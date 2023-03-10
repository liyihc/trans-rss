import asyncio
from functools import partial
import pywebio
from pywebio import input, output, session

from .. import actions, config
from ..sql import Connection, Subscribe
from ..common import SubStatus, status
from ..logger import trans_rss_logger

from .common import generate_header, catcher


async def update():
    cnt = 0
    async for name, title in actions.update(output.toast):
        cnt += 1
        output.toast(f"订阅 {name} 下载 {title}")
        await asyncio.sleep(0.5)
    if cnt:
        output.toast(f"共添加{cnt}个新下载项", color="success")
    else:
        output.toast(f"未找到有更新的订阅", color="success")
    await asyncio.sleep(2)


@catcher
async def subscribe_del_confirm(name: str, url: str):
    with Connection() as conn:
        trans_rss_logger.info(f"delete subscribe {name} {url}")
        conn.subscribe_del(name)
        output.toast(f"删除 {name}", color="success")
    session.go_app("sub-list", False)

@catcher
async def subscribe_del(name: str, url: str):
    with output.popup(f"确定删除订阅 {name} 吗"):
        output.put_buttons(
            [
                {
                    "label": "确定",
                    "value": True,
                    "color": "danger"
                },
                {
                    "label": "取消",
                    "value": False,
                    "type": "cancel",
                    "color": "secondary"
                }
            ], [
                lambda : subscribe_del_confirm(name, url),
                output.close_popup
            ]
        )

@catcher
async def subscribe_all(sub: Subscribe):
    with Connection() as conn:
        trans_rss_logger.info(f"add subscribe {sub.name} {sub.url}")
        output.toast(f"添加订阅 {sub.name}")
        conn.subscribe(sub.name, sub.url)
    await update()
    session.go_app("sub-list", False)


def download_url(url: str):
    with Connection() as conn:
        conn.download_add(url)


@catcher
async def subscribe_to(sub: Subscribe, url: str):
    with Connection() as conn:
        trans_rss_logger.info(f"add subscribe {sub.name} {sub.url}")
        trans_rss_logger.info(f"mark download {sub.name} {url}")
        conn.download_add(url)
        output.toast(f"添加订阅 {sub.name}")
        conn.subscribe(sub.name, sub.url)
    await update()
    session.go_app("sub-list", False)


@catcher
async def update_manual():
    await update()
    session.go_app("sub-list", False)


def generate_sub_table():
    with Connection() as conn:
        table = [
            "名称 最新话 更新时间 轮询时间 操作".split()
        ]
        for sub in conn.subscribe_list():
            row = [output.put_link(sub.name, f"/web/?app=subscribe-manage&name={sub.name}")]
            if sub.name in status:
                ss = status[sub.name]
                download = conn.download_get(ss.torrent)
                row.extend([
                    output.put_link(ss.title, ss.link),
                    output.put_link(
                        str(download.dt if download else ""), ss.torrent),
                    output.put_text(str(ss.query_time or ""))])
            else:
                row.extend([
                    output.put_text(""),
                    output.put_text(""),
                    output.put_text(""),
                ])
            row.append(
                output.put_button("删除", partial(subscribe_del, sub.name), "danger"))
            table.append(row)

        output.put_table(table)


@pywebio.config(title="Trans RSS 订阅列表", theme="dark")
@catcher
async def sub_list_page():
    generate_header()
    with output.use_scope("table"):
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
    with output.use_scope("table"):
        generate_sub_table()
    with output.use_scope("subscribe"):
        with Connection() as conn:
            data = await input.input_group(
                "订阅",
                [
                    input.input("名称", name="name"),
                    input.input("链接", input.URL, name="url", help_text="目前仅支持acg.rip的RSS订阅")
                ]
            )

            sub = Subscribe(**data)
            sub_all = partial(subscribe_all, sub)
            output.put_button("全部订阅", onclick=sub_all)
            async for title, link, torrent in actions.subscribe(sub):
                if conn.download_exist(torrent):
                    output.put_row(
                        [
                            output.put_text("已下载"),
                            output.put_link(title, link)
                        ], "auto"
                    )
                else:
                    output.put_row(
                        [
                            output.put_button("下载到此截止", onclick=partial(
                                subscribe_to, sub, torrent)),
                            output.put_link(title, link),
                        ]
                    )
            output.put_button("全部订阅", onclick=sub_all)
