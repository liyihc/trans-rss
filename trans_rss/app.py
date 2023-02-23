import re
from typing import List
from fastapi import FastAPI
import httpx
from fastapi_utils.tasks import repeat_every
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

title_pattern = re.compile(r'<title>([^<>]*)</title>')
torrent_pattern = re.compile(r'http[^"]*\.torrent')


@app.post("/api/manual_update")
async def update():
    ret = []
    trans_client = config.trans_client()
    with Connection() as conn:
        async with httpx.AsyncClient() as client:
            for subscribe in conn.subscribe_get():
                print("subscribe", subscribe.name, subscribe.url)
                page = 1
                retry = 0
                while True:
                    req = await client.get(f"{subscribe.url}&page={page}")
                    print(subscribe.name, f"page:{page}")
                    match req.status_code:
                        case 500:  # page end
                            retry = 0
                            break
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
                                print("find", subscribe.name, title, torrent)
                                if not conn.download_exist(torrent):
                                    ret.append(torrent)
                                    print("download", subscribe.name,
                                          title, torrent)
                                    for webhook in config.webhooks:
                                        resp = await client.post(webhook, json=webhooks.feishu(
                                            subscribe.name, title, torrent
                                        ))
                                        print(webhook, resp.status_code)
                                        # TODO log when failed

                                    # TODO log when add
                                    t = trans_client.add_torrent(torrent, download_dir=str(
                                        config.base_folder / subscribe.name))
                                    conn.download_add(torrent)
                                else:
                                    print("skip", subscribe.name, title, torrent)

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
        print("routine task start")
        await update()
    else:
        print("routine task skip")
