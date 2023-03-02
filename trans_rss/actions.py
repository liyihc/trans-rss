from typing import Callable, Generator, Iterable, Tuple
from xml.dom.minidom import parseString, Element as XmlElement, Attr as XmlAttr, Document as XmlDocument
import json
from .sql import Subscribe, Connection
from .config import config
from . import webhooks
from .logger import update_logger, api_logger, exception_logger
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


def iter_rss(text: str) -> Generator[Tuple[str, str, str], None, None]:
    doml: XmlDocument = parseString(text)
    item: XmlElement
    for item in doml.getElementsByTagName("item"):
        title = xml_get_text(item.getElementsByTagName("title")[0])
        link = xml_get_text(item.getElementsByTagName("guid")[0])
        attr: XmlAttr = item.getElementsByTagName("enclosure")[0]
        torrent = attr.attributes["url"].value
        yield title, link, torrent


async def subscribe(sub: Subscribe):
    client = AsyncHTTPClient()
    page = 1
    retry = 0
    while True:
        resp = await client.fetch(f"{sub.url}&page={page}")
        match resp.code:
            case 500:  # page end
                return
            case 200:
                retry = 0
                cnt = 0
                for title, link, torrent in iter_rss(resp.body.decode()):
                    cnt += 1
                    yield title, link, torrent
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
        body = json.dumps(webhooks.feishu(name, title, torrent))
        resp = await client.fetch(
            webhook, method="POST", headers={'Content-Type': 'application/json'},
            body=body)
        print("webhook", webhook, resp.code)
        api_logger.info(f"webhook {webhook} {resp.code}")
        if not 200 <= resp.code <= 299:
            success = False
            exception_logger.info(
                f"fail to post webhook {webhook}, body={body}")
    return success


async def update(notifier: Callable[[str], None] = None):
    if not config.debug.without_transmission:
        trans_client = config.trans_client()
    with Connection() as conn:
        names = set()
        for sub in conn.subscribe_get():
            names.add(sub.name)
            update_logger.info(f"subscribe name: {sub.name} url: {sub.url}")
            print("subscribe", sub.name, sub.url)
            if notifier:
                notifier(f"正在查找 {sub.name}")
            first = True
            async for title, link, torrent in subscribe(sub):
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
                print("download", sub.name, title, torrent)
                update_logger.info(
                    f"download name: {sub.name} title: {title} link: {link} torrent: {torrent}")
                if not config.debug.without_transmission:
                    t = trans_client.add_torrent(torrent, download_dir=config.join(sub.name))
                await broadcast(sub.name, title, torrent)
                conn.download_add(torrent)
                yield sub.name, title
        for k in list(status.keys()):
            if k not in names:
                status.pop(k)
