from functools import partial
from multiprocessing.pool import AsyncResult, ThreadPool
import threading
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
from .common import iter_in_thread, status_update, status

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


def subscribe(sub: Subscribe):
    page = 1
    retry = 0
    url = sub.url
    r = urlparse(url)
    if r.query:
        url += "&page="
    else:
        url += "?page="
    while True:
        resp = requests.get(f"{url}{page}")
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


def _add_torrent(conn: sql.sql._Sql, trans_client: transmission_rpc.Client, item: RSSParseResult, dir: str):
    try:
        if config.without_transmission:
            conn.download_add(item.torrent)
        else:
            t = trans_client.add_torrent(
                item.torrent, download_dir=dir, paused=config.debug.pause_after_add)

            time.sleep(2)
            t = trans_client.get_torrent(t.id)
            try:
                torrent_file = t.torrent_file
            except:
                torrent_file = None
            conn.download_add(item.torrent, torrent_file)
    except Exception as e:
        exception_logger.exception(
            f"add torrent {item.title} {item.torrent} to transmission {str(e)}", stack_info=True)
        return f"添加下载{item.title}失败"


def broadcast(name: str, title: str, torrent: str):
    msg: List[str] = []
    for webhook in config.webhooks:
        if not webhook.enabled:
            continue
        body = webhook_types.format(
            webhook.type, f"开始下载 {title}", f"订阅任务: {name}", torrent)
        try:
            resp = requests.post(
                webhook.url, headers={'Content-Type': 'application/json'}, data=body)
            if 200 <= resp.status_code <= 299:
                logger.webhook_noti_success(
                    webhook.type, webhook.url, resp.status_code)
            else:
                logger.webhook_noti_failed(
                    webhook.type, webhook.url, resp.status_code, body)
        except Exception as e:
            logger.webhook_noti_failed(webhook.type, webhook.url, -1, body)
            exception_logger.exception(str(e), stack_info=True)
            msg.append(f"通知{webhook.url}失败，{str(e)}")
    return msg


lock = threading.Lock()


def _update_one(sub: Subscribe):
    with lock, Connection() as conn, ThreadPool() as pool:
        update_logger.info(
            f"subscribe name: {sub.name} url: {sub.url}")
        yield "msg", "info", f"正在查找 {sub.name}"

        first = True
        l: List[RSSParseResult] = []
        for item in subscribe(sub):
            if first:
                status_update(sub.name, item.title, item.gui, item.torrent)
                first = False
            if conn.download_exist(item.torrent):
                update_logger.info(
                    f"subscribe stop because exist name: {sub.name} title: {item.title} link: {item.gui} torrent: {item.torrent}")
                yield "msg", "info", f"订阅 {sub.name} 存在 {item.title}"
                break
            l.append(item)

        trans_client = None if config.without_transmission else config.trans_client()
        results: List[AsyncResult] = []
        for item in reversed(l):
            update_logger.info(
                f"download name: {sub.name} title: {item.title} link: {item.gui} torrent: {item.gui}")

            results.append(
                pool.apply_async(
                    _add_torrent, (conn, trans_client, item, config.join(sub.name))))
            results.append(
                pool.apply_async(
                    broadcast, sub.name, item.title, item.torrent))

            yield "data", sub.name, item
        pool.close()
        pool.join()
        for result in results:
            r = result.get()
            if r is not None:
                if isinstance(r, list):
                    for msg in r:
                        yield "msg", "error", msg
                else:
                    yield "msg", "error", r


async def update_one(sub: Subscribe, notifier: Callable[[str], None] = None):
    async for item in iter_in_thread(partial(_update_one, sub)):
        match item:
            case "msg", color, msg:
                if notifier is not None:
                    notifier(msg, color=color)
            case "data", name, result:
                yield name, result


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
