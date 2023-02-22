from pathlib import Path
import re
import sqlite3
from tkinter import W
from typing import List
from fastapi import FastAPI
import fastapi
import httpx
import transmission_rpc
import xml
from fastapi_utils.tasks import repeat_every
from .config import version, config
from .sql import Subscribe, Connection


app = FastAPI(title="Trans RSS", version=version)

tmp_stop = True


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


@app.post("/api/subscribe")
async def subscribe(name: str, url: str):
    with Connection() as conn:
        conn.subscribe(name, url)


@app.delete("/api/subscribe")
async def subscribe(name: str):
    with Connection() as conn:
        conn.subscribe_del(name)


@app.get("/api/subscribe", response_model=List[Subscribe])
async def subscribe():
    with Connection() as conn:
        return conn.subscribe_get()


@app.post("/api/start")
async def start():
    global tmp_stop
    tmp_stop = False
    await update()


@app.post("/api/stop")
async def stop():
    global tmp_stop
    tmp_stop = True

pattern = re.compile(r'http[^"]*\.torrent')


@app.post("/api/manual_update")
async def update():
    ret = []
    trans_client = config.trans_client()
    with Connection() as conn:
        async with httpx.AsyncClient() as client:
            for subscribe in conn.subscribe_get():
                page = 1
                retry = 0
                while True:
                    req = await client.get(f"{subscribe.url}&page={page}")
                    match req.status_code:
                        case 500:  # page end
                            retry = 0
                            break
                        case 200:
                            retry = 0
                            cnt = 0
                            for torrent in pattern.finditer(req.text):
                                cnt += 1
                                url = torrent.group()
                                if not conn.download_exist(url):
                                    ret.append(url)
                                    print("download", subscribe.name, url)
                                    for webhook in config.webhooks:
                                        await client.post(webhook, json={
                                            "msg_type": "text",
                                            "content": {
                                                "text": f"download {subscribe.name} {url}"}
                                        })

                                    trans_client.add_torrent(url)
                                    conn.download_add(url)

                            if not cnt:
                                break
                            page += 1
                        case _:
                            retry += 1
                            if retry == 10:
                                break
    return ret


@app.on_event("startup")
@repeat_every(seconds=config.subscribe_minutes * 60, wait_first=True)
async def repeat_update():
    if not tmp_stop:
        await update()
