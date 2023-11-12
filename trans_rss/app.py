from functools import partial
from traceback import format_exc
from typing import List

import pywebio
from fastapi import FastAPI, Request, Response, responses, staticfiles
from fastapi_utils.tasks import repeat_every
from pydantic import BaseModel

from trans_rss.common import iter_in_thread, run_in_thread

from . import actions
from .config import config, get_repeat, set_repeat, version
from .logger import api_logger, exception_logger, update_logger
from .sql import Connection, Subscribe
from .web import routes as web_routes

app = FastAPI(title="Trans RSS", version=version)


@app.middleware("http")
async def log_api(request: Request, call_next):
    try:
        response: Response = await call_next(request)
        api_logger.info(
            f"{request.method} {response.status_code}, {request.client}, {request.url}")
        return response
    except Exception as e:
        api_logger.info(
            f"{request.method} {500}, {request.client.host}, {request.url}")
        exception_logger.exception(str(e), stack_info=True)
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
    with Connection() as conn:
        pass  # test db
    if not config.without_transmission:
        try:  # tes transmission
            client = config.transmission.client()
            client.get_torrents(timeout=2)
        except Exception as e:
            exception_logger.exception(str(e), stack_info=True)
            config.without_transmission = True


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


async def repeat_update():
    if get_repeat():
        try: # catch exception to avoid tries
            update_logger.info("routine task start")
            async for _ in actions.update():
                pass
        except:
            pass
    else:
        update_logger.info("routine task skip")

app.on_event("startup")(
    repeat_every(seconds=config.subscribe_minutes * 60, wait_first=True)(
        repeat_update))

app.on_event("startup")(
    repeat_every(seconds=30, wait_first=True, max_repetitions=1)(
        repeat_update))
