import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from typing import Callable, Generator, Iterable, List, Tuple
from urllib.parse import urlparse
from xml.dom.minidom import parseString, Element as XmlElement, Attr as XmlAttr, Document as XmlDocument
from pydantic import BaseModel
import requests

import transmission_rpc

from trans_rss import subscribe_types
from .sql import Subscribe, Connection
from .config import config
from . import webhook_types
from .logger import update_logger, api_logger, exception_logger
from . import logger
from .common import status_update, status

from trans_rss import sql


def xml_get_text(node: XmlElement):
    if node.nodeType == node.TEXT_NODE:
        return node.data
    ret = []
    d: XmlElement
    for d in node.childNodes:
        if d.nodeType == d.TEXT_NODE:
            ret.append(d.data)
    return "".join(ret)


class RSSParseResult(BaseModel):
    title: str
    gui: str
    torrent: str
    description: str


def iter_rss(hostname: str, text: str):
    sub_type = subscribe_types.get(hostname)
    assert sub_type is not None, f"请先为网站{hostname}手动添加订阅模板"
    doml: XmlDocument = parseString(text)
    item: XmlElement
    for item in doml.getElementsByTagName("item"):
        title = sub_type.get_text(item, "title")
        gui = sub_type.get_text(item, "gui")
        torrent = sub_type.get_text(item, "torrent")
        desc = sub_type.get_text(item, "description")
        yield RSSParseResult(
            title=title,
            gui=gui,
            torrent=torrent,
            description=desc)


async def subscribe(sub: Subscribe):
    page = 1
    retry = 0
    url = sub.url
    r = urlparse(url)
    if r.query:
        url += "&page="
    else:
        url += "?page="
    with ThreadPoolExecutor(1) as pool:
        loop = asyncio.get_running_loop()
        while True:
            resp = await loop.run_in_executor(pool, requests.get, f"{url}{page}")
            hostname = urlparse(sub.url).hostname
            match resp.status_code:
                case 500:  # page end
                    return
                case 200:
                    retry = 0
                    cnt = 0
                    for result in iter_rss(hostname, resp.text):
                        cnt += 1
                        yield result
                    if not cnt:
                        return
                    page += 1
                case _:
                    retry += 1
                    if retry == 10:
                        return
            if not config.auto_page:
                return

def _add_torrent(conn: sql.sql._Sql, trans_client: transmission_rpc.Client, item: RSSParseResult, dir:str):
    if config.without_transmission:
        conn.download_add(item.torrent)
    else:
        t = trans_client.add_torrent(item.torrent, download_dir=dir)

        time.sleep(2)
        t = trans_client.get_torrent(t.id)
        try:
            conn.download_add(item.torrent, t.torrent_file)
        except:
            conn.download_add(item.torrent)


def broadcast(name: str, title: str, torrent: str):
    success = True
    for webhook in config.webhooks:
        if not webhook.enabled:
            continue
        body = webhook_types.format(
            webhook.type, f"开始下载 {title}", f"订阅任务: {name}", torrent)
        resp = requests.post(
            webhook.url, headers={'Content-Type': 'application/json'}, data=body)
        print("webhook", webhook.type, webhook.url, resp.status_code)
        if 200 <= resp.status_code <= 299:
            logger.webhook_noti_success(
                webhook.type, webhook.url, resp.status_code)
        else:
            success = False
            logger.webhook_noti_failed(
                webhook.type, webhook.url, resp.status_code, body)
    return success


lock = asyncio.Lock()


async def update_one(sub: Subscribe, notifier: Callable[[str], None] = None):
    async with lock:
        with Connection() as conn, ThreadPoolExecutor() as pool:
            loop = asyncio.get_running_loop()

            update_logger.info(
                f"subscribe name: {sub.name} url: {sub.url}")
            print("subscribe", sub.name, sub.url)
            if notifier:
                notifier(f"正在查找 {sub.name}")

            first = True
            l: List[RSSParseResult] = []
            futures = []
            async for item in subscribe(sub):
                if first:
                    status_update(sub.name, item.title, item.gui, item.torrent)
                    first = False
                if conn.download_exist(item.torrent):
                    print("torrent exist:", sub.name, item.title, item.torrent)
                    print("subscribe stop", sub.name)
                    update_logger.info(
                        f"subscribe stop because exist name: {sub.name} title: {item.title} link: {item.gui} torrent: {item.torrent}")
                    if notifier:
                        notifier(f"订阅 {sub.name} 存在 {item.title}")
                    break
                print("find", sub.name, item.title, item.torrent)
                l.append(item)

            trans_client = None if config.without_transmission else config.trans_client()
            for item in reversed(l):
                print("download", sub.name, item.title, item.torrent)
                update_logger.info(
                    f"download name: {sub.name} title: {item.title} link: {item.gui} torrent: {item.gui}")

                futures.append(
                    loop.run_in_executor(
                        pool, _add_torrent, conn, trans_client, item, config.join(sub.name)))

                futures.append(
                    loop.run_in_executor(
                        pool, broadcast, sub.name, item.title, item.torrent))
                yield sub.name, item
            await asyncio.gather(*futures)


async def update(notifier: Callable[[str], None] = None):
    with Connection() as conn:
        names = set()
        for sub in conn.subscribe_list():
            names.add(sub.name)
            async for it in update_one(sub, notifier):
                yield it

        for k in list(status.keys()):
            if k not in names:
                status.pop(k)
