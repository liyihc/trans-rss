import asyncio
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, List, Literal, Tuple
import requests

from transmission_rpc import TransmissionError
import pywebio
from pydantic import BaseModel
from pywebio import input, output, session

from trans_rss.common import iter_in_thread, run_in_thread

from .. import actions
from ..config import config
from .. import logger
from ..sql import Connection, Subscribe
from .common import catcher, generate_header, button, requests_get


async def refresh(): 
    await asyncio.sleep(.5)
    session.run_js("location.reload()")


@catcher
async def get_id(title: str, torrent_url: str, dir:str):
    if config.without_transmission:
        output.toast("当前为独立模式，无法操纵transmission", color='warn')
        return
    client = config.trans_client()
    try:
        resp = await run_in_thread(requests_get, torrent_url)
        torrent = client.add_torrent(resp.content, download_dir=dir, paused=True)

        await asyncio.sleep(1)
        torrent = client.get_torrent(torrent.id)

        logger.manual("download", torrent_url, title)
        output.toast(f"添加新任务 {title}，请手动开始")
    except TransmissionError as e:
        resp = e.response
        assert "duplicate torrent" == resp["result"]
        torrent_id = resp["arguments"]["torrent-duplicate"]["id"]
        torrent = client.get_torrent(torrent_id)
        logger.manual("retrieve", torrent_url, title)
    with Connection() as conn:
        conn.download_assign(torrent_url, torrent.torrent_file)

    await refresh()


@catcher
async def manage_download(title: str, id: int, torrent_url: str, action: Literal["start", "stop", "delete"]):
    client = config.trans_client()
    match action:
        case "start":
            client.start_torrent(id)
            logger.manual("start", torrent_url, title)
            output.toast(f"已开始下载 {title}", color="success")
        case "stop":
            client.stop_torrent(id)
            logger.manual("stop", torrent_url, title)
            output.toast(f"已停止下载 {title}", color="success")
        case "delete":
            confirm = await input.actions(f"确定删除 {title} 吗", [button("确定", True, "danger"), button("取消", False, "success")])
            if not confirm:
                return
            if config.without_transmission:
                output.toast("当前为独立模式，无法操纵transmission", color='warn')
                return
            logger.manual("delete", torrent_url, title)
            with Connection() as conn:
                conn.download_assign(torrent_url, None)
            config.trans_client().remove_torrent(id, True)
            output.toast(f"已在transmission中删除 {title}")

    await refresh()


@pywebio.config(title="订阅管理", theme="dark")
@catcher
async def manage_subscribe_page():
    generate_header()
    table = ["标题 下载链接 下载日期 下载状态 操作".split()]

    name = await session.eval_js("new URLSearchParams(window.location.search).get('name')")
    if not name:
        output.put_markdown(f"# {name} 的订阅")
        output.put_table(table)
        return
    session.set_env(title=f"{name} 的订阅管理")
    with Connection() as conn:
        sub = conn.subscribe_get(name)
        output.put_markdown(f"# [{name}]({sub.url}) 的订阅")
        if not config.without_transmission:
            trans_client = config.trans_client()
            torrents = {t.torrent_file: t for t in trans_client.get_torrents()}
        else:
            torrents = {}
        async for clear, item in subscribe_and_cache(sub):
            row = [
                output.put_link(item.title, item.gui, new_window=True),
                output.put_link("种子", item.torrent, new_window=True)
            ]
            download = conn.download_get(item.torrent)
            if download:
                row.append(output.put_text(str(download.dt)))
                torrent = torrents.get(download.local_torrent, None)
                if torrent is not None:
                    row.extend([
                        output.put_text(torrent.status, torrent.progress),
                        output.put_buttons([
                            button("启动", "start", "success") if torrent.stopped else button(
                                "停止", "stop", "danger"),
                            button("删除", "delete", "danger"),
                        ],
                            partial(manage_download, item.title,
                                    torrent.id, item.torrent),)
                    ])
                else:
                    row.extend([
                        output.put_text("未链接"),
                        output.put_button(
                            "添加/获取下载", partial(get_id, item.title, item.torrent, config.join(sub.name)))
                    ])
            else:
                row.extend([
                    output.put_text("-"),
                    output.put_text("-"),
                    output.put_button(
                        "添加下载", partial(get_id, item.title, item.torrent, config.join(sub.name)))
                ])
            table.append(row)
            if clear:
                with output.use_scope("manage", True):
                    output.put_table(table)
        with output.use_scope("manage", True):
            output.put_table(table)


class Cache(BaseModel):
    dt: datetime
    rets: List[actions.RSSParseResult]


caches: Dict[str, Cache] = {}


async def subscribe_and_cache(sub: Subscribe):
    now = datetime.now()
    hour = timedelta(hours=1)
    need_sub = True
    if sub.url in caches:
        cache = caches[sub.url]
        if now - cache.dt < hour:
            need_sub = False
            for ret in cache.rets:
                yield False, ret
    cache = Cache(dt=now, rets=[])
    if need_sub:
        async for ret in iter_in_thread(actions.subscribe, sub):
            cache.rets.append(ret)
            yield True, ret
        caches[sub.url] = cache

    for url, cache in list(caches.items()):
        if now - cache.dt > hour:
            caches.pop(url)
