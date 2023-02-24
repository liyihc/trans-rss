import re
from typing import List
from fastapi import FastAPI
import httpx
from fastapi_utils.tasks import repeat_every
from pydantic import BaseModel
from .config import version, config
from .sql import Subscribe, Connection
from . import webhooks


app = FastAPI(title="Trans RSS", version=version)

tmp_stop = False


@app.get("/")
def hello():
    return "Hello world"


@app.on_event("startup")
async def test_transmission():
    with Connection() as conn:
        pass
    client = config.trans_client()
    client.get_torrents(timeout=2)


@app.get("/api/test-sql")
async def hello(sql_statement: str):
    with Connection() as conn:
        cursor = conn.conn.execute(sql_statement)
        return cursor.fetchall()


class Torrent(BaseModel):
    title: str
    url: str


@app.post("/api/subscribe", response_model=List[Torrent])
async def subscribe(name: str, url: str):
    with Connection() as conn:
        conn.subscribe(name, url)
        sub = Subscribe(name=name, url=url)
        return [Torrent(title=title, url=torrent) async for title, torrent in subscribe_url(sub)]


@app.delete("/api/subscribe")
async def subscribe(name: str):
    with Connection() as conn:
        conn.subscribe_del(name)


@app.get("/api/subscribe", response_model=List[Subscribe])
async def subscribe():
    with Connection() as conn:
        return conn.subscribe_get()


@app.post("/api/mark_download")
async def mark_download(torrent: str):
    with Connection() as conn:
        return conn.download_add(torrent)


@app.post("/api/start")
async def start():
    global tmp_stop
    tmp_stop = False
    await update()


@app.post("/api/stop")
async def stop():
    global tmp_stop
    tmp_stop = True

title_pattern = re.compile(r'<title>([^<>]*)</title>')
torrent_pattern = re.compile(r'http[^"]*\.torrent')


async def subscribe_url(sub: Subscribe):
    async with httpx.AsyncClient() as client:
        page = 1
        retry = 0
        while True:
            req = await client.get(f"{sub.url}&page={page}")
            match req.status_code:
                case 500:  # page end
                    return
                case 200:
                    retry = 0
                    cnt = 0
                    it = title_pattern.finditer(req.text)
                    next(it)
                    for title, torrent in zip(
                            it,
                            torrent_pattern.finditer(req.text)):
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
    async with httpx.AsyncClient() as client:
        for webhook in config.webhooks:
            resp = await client.post(webhook, json=webhooks.feishu(name, title, torrent))
            print("webhook", webhook, resp.status_code)
            # TODO log when failed


@app.post("/api/manual_update")
async def update():
    ret = []
    trans_client = config.trans_client()
    with Connection() as conn:
        for sub in conn.subscribe_get():
            print("subscribe", sub.name, sub.url)
            async for title, torrent in subscribe_url(sub):
                if conn.download_exist(torrent):
                    print("torrent exist:", sub.name, title, torrent)
                    print("subscribe stop", sub.name)
                    break
                print("download", sub.name, title, torrent)
                await broadcast(sub.name, title, torrent)

                t = trans_client.add_torrent(torrent, download_dir=str(
                    config.base_folder / sub.name))
                conn.download_add(torrent)
    return ret


@app.on_event("startup")
@repeat_every(seconds=config.subscribe_minutes * 60, wait_first=True)
async def repeat_update():
    if not tmp_stop:
        print("routine task start")
        await update()
    else:
        print("routine task skip")
