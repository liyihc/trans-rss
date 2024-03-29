from functools import partial
from typing import Literal
import pywebio
from pywebio import input, output, session

from .. import actions
from ..sql import Connection, Subscribe
from ..common import executor, sub_status
from ..config import config

from .common import button, generate_header, catcher
from .manage import subscribe_and_cache, clear_cache
from trans_rss.logger import logger

TAG = "Web_Subscribe"


@catcher
async def subscribe_del(name: str, url: str):
    result: Literal["both", "torrent", "none"] = await input.radio(
        f"确定移除订阅 {name} 吗",
        [{
            "label": "删除订阅、种子及文件", "value": "both"
        }, {
            "label": "删除订阅、种子", "value": "torrent",
        }, {
            "label": "仅删除订阅", "value": "none"
        }], value="none"
    )

    del_file = result == "both"
    del_torrent = result != "none"
    with Connection() as conn:
        sub = conn.subscribe_get(name)
        if del_torrent:
            if config.without_transmission:
                output.toast("当前为独立模式，无法操纵transmission", color='warn')
                return
            logger.warn(
                TAG, f"subscribe_del del-torrent:True del-file:{del_file} {name} {sub.url}")
            trans_client = config.transmission.client()
            torrents = {
                t.torrent_file: t for t in trans_client.get_torrents()}
            async for _, item in subscribe_and_cache(sub):
                download = conn.download_get(item.torrent)
                if download is None:
                    continue
                torrent = torrents.get(download.local_torrent, None)
                if torrent is None:
                    output.toast(f"未找到对应的种子，跳过：{item.title}")
                else:
                    trans_client.remove_torrent(
                        torrent.id, delete_data=del_file)
                    if del_file:
                        output.toast(
                            f"已删除对应的种子及文件：{item.title}", color="success")
                    else:
                        output.toast(
                            f"已删除对应的种子：{item.title}", color="success")
                    logger.warn(
                        TAG, f"subscribe_del del-torrent {item.torrent} {item.title}")
            clear_cache(sub)

        logger.warn(TAG, f"subscribe_del del-sub {name} {sub.url}")
        conn.subscribe_del(name)
        output.toast(f"删除订阅 {name}", color="success")
    generate_sub_table()


@catcher
async def subscribe_all(sub: Subscribe):
    with Connection() as conn:
        logger.info(
            TAG, f"subscribe_all {sub.name} {sub.url} {sub.include_words} {sub.exclude_words}")
        conn.subscribe(sub)
        output.toast(f"添加订阅 {sub.name}")
    actions.update_timer.update()
    session.go_app("sub-list", False)


def download_url(url: str):
    with Connection() as conn:
        conn.download_add(url)


@catcher
async def subscribe_to(sub: Subscribe, url: str):
    with Connection() as conn:
        logger.info(
            TAG, f"subscribe_to sub {sub.name} {sub.url} {sub.include_words} {sub.exclude_words}")
        logger.info(TAG, f"subscribe_to to {url}")
        conn.download_add(url)
        output.toast(f"添加订阅 {sub.name}")
        conn.subscribe(sub)
    actions.update_timer.update()
    session.go_app("sub-list", False)


@catcher
async def update_manual():
    logger.debug(TAG, "update_manual")
    actions.update_timer.update()


def generate_sub_table():
    with output.use_scope("table", True), Connection() as conn:
        table = ["名称 最新话 更新时间 轮询时间 操作".split()]
        for sub in conn.subscribe_list():
            row = [output.put_link(
                sub.name, f"/web/?app=subscribe-manage&name={sub.name}")]
            ss = sub_status.status_get(sub.name)
            if ss is not None:
                download = conn.download_get(ss.torrent)
                row.extend([
                    output.put_link(ss.title, ss.link, new_window=True),
                    output.put_link(
                        str(download.dt if download else ""), ss.torrent, new_window=True),
                    output.put_error(f"{ss.query_time or ''}更新失败") if ss.last_error else output.put_text(str(ss.query_time or ""))])
            else:
                row.extend([
                    output.put_text(""),
                    output.put_text(""),
                    output.put_text(""),
                ])
            row.append(
                output.put_button("删除", partial(subscribe_del, sub.name, sub.url), "danger"))
            table.append(row)

        output.put_table(table)
        msg = sub_status.get_status_error_msg()
        if msg:
            output.put_error(msg)


@pywebio.config(title="Trans RSS 订阅列表", theme="dark")
@catcher
async def sub_list_page():
    generate_header()
    generate_sub_table()

    output.put_buttons(
        [
            {"label": "立即更新", "value": None, "color": "success"},
            {"label": "添加新订阅", "value": None, "color": "success"}
        ],
        [
            update_manual,
            partial(session.go_app, "subscribe", False)
        ]
    )


@pywebio.config(title="Trans RSS 添加新订阅", theme="dark")
@catcher
async def subscribe_page():
    generate_header()
    generate_sub_table()

    with Connection() as conn:
        data = await input.input_group(
            "订阅",
            [
                input.input("名称", name="name"),
                input.input("链接", input.URL, name="url",
                            help_text=""),
                input.input("必须包含的词", name="include_words",
                            help_text="使用空格分开"),
                input.input("排除的词", name="exclude_words",
                            help_text="使用空格分开"),
            ]
        )

        sub = Subscribe(**data)
        sub.url = sub.url.strip()
        sub.include_words = sub.include_words.strip()
        sub.exclude_words = sub.exclude_words.strip()
        sub_all = partial(subscribe_all, sub)
        output.put_button("全部订阅", onclick=sub_all)
        async for item in executor.iter_in_thread(actions.subscribe, sub):
            if conn.download_exist(item.torrent):
                output.put_row(
                    [
                        output.put_text("已下载"),
                        output.put_link(item.title, item.gui, new_window=True)
                    ], "auto"
                )
            else:
                output.put_row(
                    [
                        output.put_button("订阅并下载以上剧集", onclick=partial(
                            subscribe_to, sub, item.torrent)),
                        output.put_link(item.title, item.gui, new_window=True),
                    ], "auto"
                )
        output.put_button("全部订阅", onclick=sub_all)
