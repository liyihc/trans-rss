import json
import re
from .sql import Subscribe, Connection
from .config import config
from . import webhooks
from tornado.httpclient import AsyncHTTPClient, HTTPRequest


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
        resp = await client.fetch(
            webhook, method="POST", headers={'Content-Type': 'application/json'},
            body=json.dumps(webhooks.feishu(name, title, torrent))
        )
        print("webhook", webhook, resp.code)
        # TODO log when failed


async def update():
    ret = []
    if not config.debug.without_transmission:
        trans_client = config.trans_client()
    with Connection() as conn:
        for sub in conn.subscribe_get():
            print("subscribe", sub.name, sub.url)
            async for title, torrent in subscribe(sub):
                if conn.download_exist(torrent):
                    print("torrent exist:", sub.name, title, torrent)
                    print("subscribe stop", sub.name)
                    break
                print("download", sub.name, title, torrent)
                await broadcast(sub.name, title, torrent)

                if not config.debug.without_transmission:
                    t = trans_client.add_torrent(torrent, download_dir=str(
                        config.base_folder / sub.name))
                conn.download_add(torrent)
                ret.append((sub.name, title))
    return ret
