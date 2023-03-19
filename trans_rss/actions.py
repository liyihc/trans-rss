import asyncio
from typing import Callable, Generator, Iterable, List, Tuple
from urllib.parse import urlparse
from xml.dom.minidom import parseString, Element as XmlElement, Attr as XmlAttr, Document as XmlDocument
import json

from trans_rss import subscribe_types
from .sql import Subscribe, Connection
from .config import config
from . import webhook_types
from .logger import update_logger, api_logger, exception_logger
from . import logger
from .common import status_update, status
from tornado.httpclient import AsyncHTTPClient


def xml_get_text(node: XmlElement):
    if node.nodeType == node.TEXT_NODE:
        return node.data
    ret = []
    d: XmlElement
    for d in node.childNodes:
        if d.nodeType == d.TEXT_NODE:
            ret.append(d.data)
    return "".join(ret)


def iter_rss(hostname: str, text: str) -> Generator[Tuple[str, str, str], None, None]:
    sub_type = subscribe_types.get(hostname)
    doml: XmlDocument = parseString(text)
    item: XmlElement
    for item in doml.getElementsByTagName("item"):
        title = sub_type.get_text(item, "title")
        gui = sub_type.get_text(item, "gui")
        torrent = sub_type.get_text(item, "torrent")
        desc = sub_type.get_text(item, "description")
        yield title, gui, torrent, desc


async def subscribe(sub: Subscribe):
    client = AsyncHTTPClient()
    page = 1
    retry = 0
    while True:
        resp = await client.fetch(f"{sub.url}&page={page}")
        hostname = urlparse(sub.url).hostname
        match resp.code:
            case 500:  # page end
                return
            case 200:
                retry = 0
                cnt = 0
                for title, link, torrent, description in iter_rss(hostname, resp.body.decode()):
                    cnt += 1
                    yield title, link, torrent, description
                if not cnt:
                    return
                page += 1
            case _:
                retry += 1
                if retry == 10:
                    return


async def broadcast(name: str, title: str, torrent: str):
    client = AsyncHTTPClient()
    success = True
    for webhook in config.webhooks:
        if not webhook.enabled:
            continue
        body = webhook_types.format(webhook.type, f"开始下载 {title}", f"订阅任务: {name}", torrent)
        resp = await client.fetch(
            webhook.url, method="POST", headers={'Content-Type': 'application/json'},
            body=body)
        print("webhook", webhook.type, webhook.url, resp.code)
        if 200 <= resp.code <= 299:
            logger.webhook_noti_success(webhook.type, webhook.url, resp.code)
        else:
            success = False
            logger.webhook_noti_failed(webhook.type, webhook.url, resp.code, body)
    return success

lock = asyncio.Lock()

async def update(notifier: Callable[[str], None] = None):
    async with lock:
        if not config.debug.without_transmission:
            trans_client = config.trans_client()
        with Connection() as conn:
            names = set()
            for sub in conn.subscribe_list():
                names.add(sub.name)
                update_logger.info(f"subscribe name: {sub.name} url: {sub.url}")
                print("subscribe", sub.name, sub.url)
                if notifier:
                    notifier(f"正在查找 {sub.name}")
                first = True
                l: List[Tuple[str, str, str]] = []
                async for title, link, torrent, description in subscribe(sub):
                    if first:
                        status_update(sub.name, title, link, torrent)
                        first = False
                    if conn.download_exist(torrent):
                        print("torrent exist:", sub.name, title, torrent)
                        print("subscribe stop", sub.name)
                        update_logger.info(
                            f"subscribe stop because exist name: {sub.name} title: {title} link: {link} torrent: {torrent}")
                        if notifier:
                            notifier(f"订阅 {sub.name} 存在 {title}")
                        break
                    print("find", sub.name, title, torrent)
                    l.append((title, link, torrent))
                for title, link, torrent in reversed(l):
                    print("download", sub.name, title, torrent)
                    update_logger.info(
                        f"download name: {sub.name} title: {title} link: {link} torrent: {torrent}")
                    if not config.debug.without_transmission:
                        t = trans_client.add_torrent(
                            torrent, download_dir=config.join(sub.name))
                        conn.download_add(torrent, t.id)
                    else:
                        conn.download_add(torrent)
                    await broadcast(sub.name, title, torrent)
                    yield sub.name, title
            for k in list(status.keys()):
                if k not in names:
                    status.pop(k)
