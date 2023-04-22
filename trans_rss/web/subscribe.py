import asyncio
from functools import partial
import pywebio
from pywebio import input, output, session

from .. import actions
from ..sql import Connection, Subscribe
from ..common import SubStatus, iter_in_thread, status, get_status_error_msg
from ..config import config

from .common import button, generate_header, catcher
from .manage import subscribe_and_cache
from trans_rss import logger


async def update(sub: Subscribe = None):
    cnt = 0
    async for name, item in actions.update(output.toast) \
            if sub is None else actions.update_one(sub, output.toast):
        cnt += 1
        output.toast(f"订阅 {name} 下载 {item.title}")
        await asyncio.sleep(0.5)
    if cnt:
        output.toast(f"共添加{cnt}个新下载项", color="success")
    else:
        output.toast(f"未找到有更新的订阅", color="success")
    await asyncio.sleep(2)


@catcher
async def subscribe_del(name: str, url: str):
    confirm = await input.actions(
        f"确定删除订阅 {name} 吗",
        [
            button("确定并同时删除种子", 2, "danger"),
            button("确定", 1, "danger"), button("取消", 0, "secondary")])
    if confirm:
        if confirm == 2:
            if config.without_transmission:
                output.toast("当前为独立模式，无法操纵transmission", color='warn')
                return

        with Connection() as conn:
            sub = conn.subscribe_get(name)
            if confirm == 2:
                logger.subscribe("delete-file", name, sub.url)
                trans_client = config.trans_client()
                torrents = {
                    t.torrent_file: t for t in trans_client.get_torrents()}
                async for _, item in subscribe_and_cache(sub):
                    download = conn.download_get(item.torrent)
                    torrent = torrents.get(download.local_torrent, None)
                    if torrent is None:
                        output.toast(f"未找到对应的种子，跳过：{item.title}")
                    else:
                        trans_client.remove_torrent(
                            torrent.id, delete_data=True)
                        output.toast(
                            f"已删除对应的种子及文件：{item.title}", color="success")
                        logger.manual("delete", item.torrent, item.title)

            logger.subscribe("delete", name, sub.url)
            conn.subscribe_del(name)
            output.toast(f"删除订阅 {name}", color="success")
        generate_sub_table()


@catcher
async def subscribe_all(sub: Subscribe):
    with Connection() as conn:
        logger.subscribe("add", sub.name, sub.url)
        conn.subscribe(sub.name, sub.url)
        output.toast(f"添加订阅 {sub.name}")
    await update(sub)
    generate_sub_table()


def download_url(url: str):
    with Connection() as conn:
        conn.download_add(url)


@catcher
async def subscribe_to(sub: Subscribe, url: str):
    with Connection() as conn:
        logger.subscribe("add", sub.name, sub.url)
        logger.manual("mark", url, sub.name, sub.url)
        conn.download_add(url)
        output.toast(f"添加订阅 {sub.name}")
        conn.subscribe(sub.name, sub.url)
    await update(sub)
    session.go_app("sub-list", False)


@catcher
async def update_manual():
    await update()
    generate_sub_table()


def generate_sub_table():
    with output.use_scope("table", True), Connection() as conn:
        table = ["名称 最新话 更新时间 轮询时间 操作".split()]
        for sub in conn.subscribe_list():
            row = [output.put_link(
                sub.name, f"/web/?app=subscribe-manage&name={sub.name}")]
            if sub.name in status:
                ss = status[sub.name]
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
        msg = get_status_error_msg()
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
                            help_text="")
            ]
        )

        sub = Subscribe(**data)
        sub_all = partial(subscribe_all, sub)
        output.put_button("全部订阅", onclick=sub_all)
        async for item in iter_in_thread(actions.subscribe, sub):
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
