import asyncio
from functools import partial
from multiprocessing.pool import AsyncResult, ThreadPool
import threading
import time
from typing import Callable, Generator, Iterable, List, Tuple
from urllib.parse import urlparse
from xml.dom.minidom import parseString, Element as XmlElement, Attr as XmlAttr, Document as XmlDocument
from pydantic import BaseModel
import requests

from trans_rss import subscribe_types
from .sql import Subscribe, Connection
from .config import config
from . import webhook_types
from .logger import logger, update_logger
from .common import emit_message, get_status_error_msg, iter_in_thread, run_in_thread, set_status_error_msg, status_error, status_update, status

TAG = "Actions"


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
    proxies = config.get_proxies()
    include_words = set(sub.include_words.split())
    exclude_words = set(sub.exclude_words.split())
    while True:
        resp = requests.get(
            f"{url}{page}", headers=config.get_headers(), proxies=proxies)
        hostname = urlparse(sub.url).hostname
        match resp.status_code:
            case 500:  # page end
                return
            case 200:
                retry = 0
                cnt = 0
                for result in iter_rss(hostname, resp.text):
                    cnt += 1
                    title = result.title
                    update_logger.info(TAG, f"subscribe find-new {sub.name} {result.title} {result.gui} {result.torrent}")
                    exclude = False
                    for word in include_words:
                        if word not in title:
                            exclude = True
                            update_logger.info(TAG, f"subscribe exclude {result.title} because without {word}")
                            break
                    if exclude:
                        continue
                    for word in exclude_words:
                        if word in title:
                            exclude = True
                            update_logger.info(TAG, f"subscribe exclude {result.title} because with {word}")
                            break
                    if exclude:
                        continue
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


def _broadcast(title: str, desc: str, link: str):
    for webhook in config.webhooks:
        if not webhook.enabled:
            continue
        body = webhook_types.format(webhook.type, title, desc, link)
        try:
            resp = requests.post(
                webhook.url, headers={'Content-Type': 'application/json'}, data=body)
            if 200 <= resp.status_code <= 299:
                logger.info(
                    TAG, f"_broadcast success {webhook.type} {webhook.url} {resp.status_code}")
            else:
                logger.info(
                    TAG, f"_broadcast failed {webhook.type} {webhook.url} {resp.status_code} {body}")
        except Exception as e:
            logger.exception(
                TAG, f"_broadcast exception {webhook.type} {webhook.url} {body}")
            emit_message(f"通知{webhook.url}失败，{str(e)}", 30, color="error")


def broadcast_test():
    _broadcast("Trans-RSS测试", "测试webhook",
               "https://github.com/liyihc/trans-rss")


def broadcast_update(name: str, title: str, torrent: str):
    _broadcast(f"开始下载 {title}", f"订阅任务：{name}", torrent)


def broadcast_error(name: str, link: str):
    _broadcast("订阅失败", f"订阅{name}失败", link)


def broadcast_recovery():
    _broadcast("订阅恢复正常", f"订阅恢复正常", "")


lock = threading.Lock()


def _update_one(sub: Subscribe):
    with lock, Connection() as conn, ThreadPool() as pool:
        update_logger.info(TAG, f"udpate name: {sub.name} url: {sub.url}")

        emit_message(f"正在查找 {sub.name}")

        first = True
        l: List[RSSParseResult] = []
        for item in subscribe(sub):
            if first:
                status_update(sub.name, item.title, item.gui, item.torrent)
                first = False
            if conn.download_exist(item.torrent):
                update_logger.info(TAG,
                                   f"update stop because exist name: {sub.name} title: {item.title} link: {item.gui} torrent: {item.torrent}")
                emit_message(f"订阅 {sub.name} 存在 {item.title}")
                break
            l.append(item)

        trans_client = None if config.without_transmission else config.transmission.client()
        results: List[AsyncResult] = []
        for item in reversed(l):
            update_logger.info(
                TAG, f"update download name: {sub.name} title: {item.title} link: {item.gui} torrent: {item.gui}")

            if config.without_transmission:
                conn.download_add(item.torrent)
            else:
                resp = requests.get(
                    item.torrent, timeout=10, headers=config.get_headers(),
                    proxies=config.get_proxies())
                t = trans_client.add_torrent(
                    resp.content, download_dir=config.join(sub.name), paused=config.transmission.pause_after_add)

                time.sleep(2)
                t = trans_client.get_torrent(t.id)
                try:
                    torrent_file = t.torrent_file
                except:
                    torrent_file = None
                conn.download_add(item.torrent, torrent_file)
            results.append(
                pool.apply_async(
                    broadcast_update, (sub.name, item.title, item.torrent)))

            emit_message(f"订阅 {sub.name} 下载 {item.title}")
            yield sub.name, item
        pool.close()
        pool.join()


async def update():
    with Connection() as conn:
        subs = list(conn.subscribe_list())
        updated = set()
        error_sub: Subscribe = None
        error_msg: str = None
        names = {sub.name for sub in subs}
        try:
            cnt = 0
            for sub in subs:
                for retry in reversed(range(3)):
                    try:
                        async for name, item in iter_in_thread(partial(_update_one, sub)):
                            yield name, item
                            cnt += 1
                        updated.add(sub.name)
                        break
                    except Exception as e:
                        logger.exception(
                            TAG, f"tried {3-retry} times, {retry} times left")
                        if not retry:
                            error_sub = sub
                            raise
            if cnt:
                emit_message(f"共添加{cnt}个新下载项", color="success")
            else:
                emit_message(f"未找到有更新的订阅", color="success")
            if get_status_error_msg():
                try:
                    await run_in_thread(broadcast_recovery)
                except:
                    pass
            set_status_error_msg("")
        except Exception as e:
            errors = names.difference(updated)
            for name in errors:
                status_error(name)
            if not get_status_error_msg() and config.notify_failed_update:  # skip if notified
                try:
                    await run_in_thread(broadcast_error, error_sub.name, error_sub.url)
                except:
                    pass
            set_status_error_msg(error_msg)
            logger.exception(TAG, str(e))
            emit_message(f"订阅中出现错误 {e}", duration=30, color="error")
        finally:
            for k in list(status.keys()):
                if k not in names:
                    status.pop(k)


class _UpdateTimer:
    def __init__(self) -> None:
        self._update_timer: threading.Timer = None
        self._running = False

    def update(self, timeout_second: int = 0, repeat=False):
        if self._update_timer is not None:
            self._update_timer.cancel()
        if repeat and not self._running:
            self._running = True
        self._update_timer = threading.Timer(timeout_second, self._timeout)
        self._update_timer.daemon = True
        self._update_timer.start()

    def _timeout(self):
        async def afunc():
            try:
                update_logger.info(TAG, "routine task start")
                async for _ in update():
                    pass
            except:
                pass
        asyncio.run(afunc())
        if self._running:
            self._update_timer = None
            self.update(config.subscribe_minutes*60, repeat=True)

    def cancel(self):
        if self._update_timer is not None:
            self._update_timer.cancel()
            self._update_timer = None
        self._running = False

    @property
    def is_running(self):
        return self._running


update_timer = _UpdateTimer()
