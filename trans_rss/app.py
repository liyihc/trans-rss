from traceback import format_exc
from typing import List
from fastapi import FastAPI, Request, Response, responses
from fastapi_utils.tasks import repeat_every
from pydantic import BaseModel
from .config import version, config, get_repeat, set_repeat
from .sql import Subscribe, Connection
from .web import routes as web_routes
from . import actions
from .logger import exception_logger, update_logger, api_logger


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


app.mount("/web", FastAPI(routes=web_routes))


@app.on_event("startup")
async def test_transmission():
    with Connection() as conn:
        pass
    if not config.debug.without_transmission:
        client = config.trans_client()
        client.get_torrents(timeout=2)


@app.get("/api/test-sql")
async def test_sql(sql_statement: str):
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
        return [Torrent(title=title, url=torrent) async for title, torrent in actions.subscribe(sub)]


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
    ret = await actions.broadcast("测试", "webhook", "")
    return "success" if ret else "fail"


async def repeat_update():
    if get_repeat():
        print("routine task start")
        update_logger.info("routine task start")
        async for _ in actions.update():
            pass
    else:
        print("routine task skip")
        update_logger.info("routine task skip")

app.on_event("startup")(
    repeat_every(
        seconds=config.subscribe_minutes * 60, wait_first=True,
        logger=exception_logger)(
        repeat_update
    )
)

app.on_event("startup")(
    repeat_every(
        seconds=30, wait_first=True,
        logger=exception_logger, max_repetitions=1)(
        repeat_update
    )
)
