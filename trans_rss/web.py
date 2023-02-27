import asyncio
from functools import partial
from traceback import print_exc
from pywebio import *
from pywebio.platform.fastapi import webio_routes

from . import actions, config
from .sql import Connection, Subscribe
from .common import SubStatus, status
from .logger import exception_logger


async def update():
    cnt = 0
    async for name, title in actions.update():
        cnt += 1
        output.popup(f"订阅 {name} 添加新下载项", title)
        await asyncio.sleep(0.5)
    if cnt:
        output.popup(f"共添加{cnt}个新下载项")
    else:
        output.popup(f"未找到有更新的订阅")
    await asyncio.sleep(2)


def generate_common():
    output.put_buttons(
        ["订阅列表", "API page"],
        onclick=[
            lambda: session.go_app("sub-list", False),
            lambda: session.run_js('window.open("/docs", "_blank")')
        ])


def subscribe_del(name: str):
    with Connection() as conn:
        conn.subscribe_del(name)
    session.go_app("sub-list", False)


async def subscribe_all(sub: Subscribe):
    with Connection() as conn:
        conn.subscribe(sub.name, sub.url)
    await update()
    session.go_app("sub-list", False)


def download_url(url: str):
    with Connection() as conn:
        conn.download_add(url)


async def subscribe_to(sub: Subscribe, url: str):
    with Connection() as conn:
        conn.download_add(url)
        conn.subscribe(sub.name, sub.url)
    await update()
    session.go_app("sub-list", False)

async def update_manual():
    await update()
    session.go_app("sub-list", False)


def generate_sub_table():
    with Connection() as conn:
        table = [
            "名称 最新话 更新时间 轮询时间 操作".split()
        ]
        for sub in conn.subscribe_get():
            row = [output.put_link(sub.name, sub.url)]
            if sub.name in status:
                ss = status[sub.name]
                row.extend([
                    output.put_link(ss.title, ss.url),
                    output.put_text(str(conn.download_time(ss.url) or "")),
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


async def sub_list():
    try:
        session.set_env(title=f"Trans RSS 订阅列表")
        with output.use_scope("common"):
            generate_common()
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
    except exceptions.SessionException:
        raise
    except Exception as e:
        print(str(e))
        print_exc()
        exception_logger.exception(e, stack_info=True)
        raise


async def subscribe():
    try:
        session.set_env(title=f"Trans RSS 添加新订阅")
        with output.use_scope("common"):
            generate_common()
        with output.use_scope("table"):
            generate_sub_table()
        with output.use_scope("subscribe"):
            with Connection() as conn:
                data = await input.input_group(
                    "订阅",
                    [
                        input.input("名称", name="name"),
                        input.input("链接", input.URL, name="url")
                    ]
                )

                sub = Subscribe(**data)
                sub_all = partial(subscribe_all, sub)
                output.put_button("全部订阅", onclick=sub_all)
                async for title, torrent in actions.subscribe(sub):
                    if conn.download_exist(torrent):
                        output.put_row(
                            [
                                output.put_text("已下载"),
                                output.put_link(title, torrent)
                            ], "auto"
                        )
                    else:
                        output.put_row(
                            [
                                output.put_button("下载到此截止", onclick=partial(
                                    subscribe_to, sub, torrent)),
                                output.put_link(title, torrent),
                            ]
                        )
                output.put_button("全部订阅", onclick=sub_all)
    except exceptions.SessionException:
        raise
    except Exception as e:
        print(str(e))
        print_exc()
        exception_logger.exception(e, stack_info=True)
        raise

# async def log_page() TODO more GUI
# async def config_page()

routes = webio_routes(
    {
        "sub-list": sub_list,
        "subscribe": subscribe
    }
)
