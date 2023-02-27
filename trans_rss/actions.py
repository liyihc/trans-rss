from datetime import datetime
import json
import re
from .sql import Subscribe, Connection
from .config import config
from . import webhooks
from .logger import update_logger, api_logger, exception_logger
from .common import status_update, status
from tornado.httpclient import AsyncHTTPClient


title_pattern = re.compile(r'<title>([^<>]*)</title>')
torrent_pattern = re.compile(r'http[^"]*\.torrent')


async def subscribe(sub: Subscribe):
    client = AsyncHTTPClient()
    page = 1
    retry = 0
    while True:
        req = await client.fetch(f"{sub.url}&page={page}")
        match req.code:
            case 500:  # page end
                return
            case 200:
                retry = 0
                cnt = 0
                text = req.body.decode()
                it = title_pattern.finditer(text)
                next(it)
                for title, torrent in zip(
                        it,
                        torrent_pattern.finditer(text)):
                    title = title.group(1)
                    torrent = torrent.group()
                    cnt += 1
                    yield title, torrent
                if not cnt:
                    return
                page += 1
            case _:
                retry += 1
                if retry == 10:
                    return


async def broadcast(name: str, title: str, torrent: str):
    client = AsyncHTTPClient()
    for webhook in config.webhooks:
        body = json.dumps(webhooks.feishu(name, title, torrent))
        resp = await client.fetch(
            webhook, method="POST", headers={'Content-Type': 'application/json'},
            body=body)
        print("webhook", webhook, resp.code)
        api_logger.info(f"webhook {webhook} {resp.code}")
        if not 200 <= resp.code <= 299:
            exception_logger.info(
                f"fail to post webhook {webhook}, body={body}")


async def update():
    if not config.debug.without_transmission:
        trans_client = config.trans_client()
    with Connection() as conn:
        names = set()
        for sub in conn.subscribe_get():
            names.add(sub.name)
            update_logger.info(f"subscribe name: {sub.name} url: {sub.url}")
            print("subscribe", sub.name, sub.url)
            first = True
            async for title, torrent in subscribe(sub):
                if conn.download_exist(torrent):
                    print("torrent exist:", sub.name, title, torrent)
                    print("subscribe stop", sub.name)
                    update_logger.info(f"subscribe stop because exist name: {sub.name} title: {title} torrent: {torrent}")
                    if first:
                        status_update(sub.name, title, True)
                    break
                if first:
                    status_update(sub.name, title, False)
                    first = False
                print("download", sub.name, title, torrent)
                update_logger.info(f"download name: {sub.name} title: {title} torrent: {torrent}")
                if not config.debug.without_transmission:
                    t = trans_client.add_torrent(torrent, download_dir=str(
                        config.base_folder / sub.name))
                await broadcast(sub.name, title, torrent)
                conn.download_add(torrent)
                yield sub.name, title
        for k in list(status.keys()):
            if k not in names:
                status.pop(k)
