import asyncio
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, List, Tuple

import pywebio
from pydantic import BaseModel
from pywebio import input, output, session

from .. import actions
from ..config import config
from ..logger import trans_rss_logger
from ..sql import Connection, Subscribe
from .common import catcher, generate_header


def refresh():
    session.run_js("location.reload()")


@catcher
async def get_id(title: str, torrent_url: str):
    if config.debug.without_transmission:
        output.toast("位于debug模式，无法操纵transmission", color='warn')
        return
    trans_rss_logger.info(f"add transmission torrent {title} {torrent_url}")
    t = config.trans_client().add_torrent(torrent_url, paused=True)
    with Connection() as conn:
        conn.download_assign(torrent_url, t.id)

    output.toast(f"已添加")
    await asyncio.sleep(.5)
    refresh()


@catcher
async def delete_confirm(title: str, id: int, torrent_url: str):
    if config.debug.without_transmission:
        output.toast("位于debug模式，无法操纵transmission", color='warn')
        return
    trans_rss_logger.info(f"delete transmission torrent {id} {title} {torrent_url}")
    with Connection() as conn:
        conn.download_assign(torrent_url, None)
    config.trans_client().remove_torrent(id, True)
    output.toast(f"已在transmission中删除 {title}")
    refresh()


@catcher
async def delete_download(title: str, id: int, torrent_url: str):
    with output.popup(f"确定删除 {title} 吗"):
        output.put_buttons(
            [
                {"label": "确定", "value": True, "color": "danger"},
                {"label": "取消", "value": False,
                    "type": "cancel", "color": "secondary"}
            ], [
                partial(delete_confirm, title, id, torrent_url),
                output.close_popup
            ]
        )


@pywebio.config(title="订阅管理", theme="dark")
@catcher
async def manage_subscribe_page():
    generate_header()
    table = ["标题 下载链接 下载日期 下载id 下载状态 操作".split()]

    name = await session.eval_js("new URLSearchParams(window.location.search).get('name')")
    if not name:
        output.put_markdown(f"# {name} 的订阅")
        output.put_table(table)
        return
    session.set_env(title=f"{name} 的订阅管理")
    with Connection() as conn:
        sub = conn.subscribe_get(name)
        output.put_markdown(f"# [{name}]({sub.url}) 的订阅")
        if not config.debug.without_transmission:
            trans_client = config.trans_client()
        async for title, url, torrent_url, clear in subscribe_and_cache(sub):
            row = [
                output.put_link(title, url),
                output.put_link("种子", torrent_url)
            ]
            download = conn.download_get(torrent_url)
            if download:
                row.append(output.put_text(str(download.dt)))
                torrent = None
                try:
                    if download.id is not None:
                        torrent = trans_client.get_torrent(download.id)
                except:
                    if not config.debug.without_transmission:
                        conn.download_assign(torrent_url, None)
                if torrent is not None:
                    row.extend([
                        output.put_text(download.id),
                        output.put_text(torrent.status, torrent.progress),
                        output.put_buttons([
                            {
                                "label": "删除",
                                "value": None,
                                "color": "danger"
                            }
                        ],
                            [
                                partial(delete_download, title,
                                        download.id, torrent_url)
                        ])
                    ])
                else:
                    row.extend([
                        output.put_text("-"),
                        output.put_text("-"),
                        output.put_button(
                            "添加下载/获取id", partial(get_id, title, torrent_url))
                    ])
            else:
                row.extend([
                    output.put_text("-") for _ in range(4)
                ])
            table.append(row)
            if clear:
                with output.use_scope("manage", True):
                    output.put_table(table)
        with output.use_scope("manage", True):
            output.put_table(table)


class Cache(BaseModel):
    dt: datetime
    rets: List[Tuple[str, str, str]]


caches: Dict[str, Cache] = {}


async def subscribe_and_cache(sub: Subscribe):
    now = datetime.now()
    hour = timedelta(hours=1)
    subscribe = True
    if sub.url in caches:
        cache = caches[sub.url]
        if now - cache.dt < hour:
            subscribe = False
            for ret in cache.rets:
                yield (*ret, False)
    cache = Cache(dt=now, rets=[])
    if subscribe:
        async for ret in actions.subscribe(sub):
            cache.rets.append(ret)
            yield (*ret, True)
        caches[sub.url] = cache

    for url, cache in list(caches.items()):
        if now - cache.dt > hour:
            caches.pop(url)
