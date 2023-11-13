from threading import Thread
from traceback import format_exc
from typing import List

import pywebio
from fastapi import FastAPI, Request, Response, responses, staticfiles

from trans_rss.common import iter_in_thread, run_in_thread, set_status_error_msg, start_emit

from . import actions
from .config import config, version
from .logger import logger
from .sql import Connection, Subscribe
from .web import routes as web_routes

app = FastAPI(title="Trans RSS", version=version)

TAG = "App"


@app.middleware("http")
async def log_api(request: Request, call_next):
    try:
        response: Response = await call_next(request)
        logger.debug(
            TAG, f"log_api {request.method} {response.status_code}, {request.client}, {request.url}")
        return response
    except Exception as e:
        logger.exception(
            TAG, f"log_api {request.method} {500}, {request.client.host}, {request.url}")
        return responses.JSONResponse(
            {"msg": str(e), "stack": format_exc()}, 500)


@app.get("/")
def web():
    return responses.RedirectResponse("/web?app=sub-list")


webio_app = FastAPI(routes=web_routes)
webio_app.mount(
    "/static", staticfiles.StaticFiles(directory=pywebio.STATIC_PATH), name="static")

app.mount("/web", webio_app)


@app.on_event("startup")
async def test_transmission():
    config.refresh()
    start_emit()
    with Connection() as conn:
        pass  # test db
    if not config.without_transmission:
        try:  # test transmission
            client = config.transmission.client()
            client.get_torrents(timeout=2)
        except Exception as e:
            logger.exception(TAG, str(e))
            config.without_transmission = True
            actions.update_timer.cancel()
            set_status_error_msg("连接不上Transmission，停止")
    if config.auto_start:
        actions.update_timer.update(5, True)


@app.get("/api/test-sql")
async def test_sql(sql_statement: str):
    with Connection() as conn:
        cursor = conn.conn.execute(sql_statement)
        return cursor.fetchall()


@app.post("/api/subscribe", response_model=List[actions.RSSParseResult])
async def subscribe(name: str, url: str):
    with Connection() as conn:
        conn.subscribe(Subscribe(name=name, url=url))
        sub = Subscribe(name=name, url=url)
        return [item async for item in iter_in_thread(actions.subscribe, sub)]


@app.delete("/api/subscribe")
async def subscribe(name: str):
    with Connection() as conn:
        conn.subscribe_del(name)


@app.get("/api/subscribe", response_model=List[Subscribe])
async def subscribe():
    with Connection() as conn:
        return conn.subscribe_list()


@app.post("/api/mark_download")
async def mark_download(torrent: str):
    with Connection() as conn:
        return conn.download_add(torrent)


@app.post("/api/start")
async def start():
    set_repeat(True)
    ret = []
    async for item in actions.update():
        ret.append(item)
    return ret


@app.post("/api/stop")
async def stop():
    set_repeat(False)


@app.post("/api/manual_update")
async def update():
    ret = []
    async for item in actions.update():
        ret.append(item)
    return ret


@app.post("/api/test_webhooks")
async def test_webhooks():
    await run_in_thread(actions.broadcast_test)
