from functools import partial
from traceback import print_exc
from pywebio import *
from pywebio.platform.fastapi import webio_routes

from . import actions, config
from .sql import Connection, Subscribe

async def update():
    cnt = 0
    async for name, title in actions.update():
        cnt += 1
        output.popup(f"订阅 {name} 添加新下载项", title)
    if cnt == 0:
        output.popup(f"未找到有更新的订阅")


def common():
    output.put_buttons(
        ["立刻手动更新", "API page"],
        onclick=[
            update,
            lambda : session.run_js('window.open("/docs", "_blank")')
        ])


def subscribe_del(name: str):
    with Connection() as conn:
        conn.subscribe_del(name)
    session.go_app("sub", False)


async def subscribe_all(sub: Subscribe):
    with Connection() as conn:
        conn.subscribe(sub.name, sub.url)
    await update()
    session.go_app("sub", False)


def download_url(url: str):
    with Connection() as conn:
        conn.download_add(url)


async def subscribe_to(sub: Subscribe, url: str):
    with Connection() as conn:
        conn.download_add(url)
        conn.subscribe(sub.name, sub.url)
    await update()
    session.go_app("sub", False)


async def subscribe():
    try:
        session.set_env(title=f"Trans RSS {config.version}")
        with Connection() as conn:
            with output.use_scope("common"):
                common()
            with output.use_scope("table"):
                table = [
                    "名称 链接 操作".split()
                ]
                for sub in conn.subscribe_get():
                    table.append(
                        [
                            sub.name,
                            output.put_link("订阅链接", sub.url),
                            output.put_button("删除", onclick=partial(
                                subscribe_del, sub.name))
                        ]
                    )
                output.put_table(table)
            with output.use_scope("subscribe"):
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
    except Exception as e:
        if not isinstance(e, exceptions.SessionException):
            print(str(e))
            print_exc()
        raise

routes = webio_routes(
    {
        "sub": subscribe,
    }
)
