import asyncio
import logging
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from threading import Thread
from time import sleep
from traceback import format_exc
from types import NoneType
from typing import (Any, AsyncGenerator, Callable, Dict, Generator, Iterable,
                    List, Literal, TypeVar, Union)

from pydantic import BaseModel

from trans_rss.logger import logger
from trans_rss.config import config

TAG = "Common"

class SubStatus(BaseModel):
    title: str
    link: str
    torrent: str
    query_time: Union[datetime, None]
    last_error: bool = False


status: Dict[str, SubStatus] = {}

_error_msg: str = ""


def status_update(name: str, title: str, link: str, torrent: str):
    status[name] = SubStatus(
        title=title, link=link, torrent=torrent,
        query_time=datetime.now().replace(microsecond=0))


def status_error(name: str):
    if name in status:
        status[name].query_time = datetime.now().replace(microsecond=0)
        status[name].last_error = True
    else:
        status[name] = SubStatus(
            title="", link="", torrent="",
            query_time=datetime.now().replace(microsecond=0), last_error=True)


def set_status_error_msg(msg: str):
    global _error_msg
    _error_msg = msg


def get_status_error_msg():
    return _error_msg


T = TypeVar("T")


@dataclass
class ThreadFuncError:
    args: Iterable[Any]
    format_exc: str


async def iter_in_thread(func: Callable[..., Generator[T, Any, Any]], *args, **kwds) -> AsyncGenerator[T, Any]:
    def new_func(q: Queue):
        try:
            for item in func(*args, **kwds):
                q.put(item)
            q.put(None)
        except Exception as e:
            logger = logging.getLogger("exception")
            logger.exception(
                f"exception in iter_in_thread\n{str(e)}", stack_info=True)
            q.put(ThreadFuncError(e.args, format_exc()))

    q = Queue()
    # create_task will start the thread
    task = asyncio.create_task(asyncio.to_thread(new_func, q))
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(1) as pool:
        while True:
            result = await loop.run_in_executor(pool, q.get)
            if isinstance(result, (ThreadFuncError, NoneType)):
                await task  # wait until the task finish
                if result is None:
                    return
                raise Exception(*result.args)
            else:
                yield result


async def run_in_thread(func: Callable[..., T], *args, **kwds) -> T:
    def new_func():
        try:
            return func(*args, **kwds)
        except Exception as e:
            logger = logging.getLogger("exception")
            logger.exception(
                f"exception in iter_in_thread\n{str(e)}", stack_info=True)
            return ThreadFuncError(e.args, format_exc())
    ret = await asyncio.to_thread(new_func)
    if isinstance(ret, ThreadFuncError):
        raise Exception(*ret.args)
    else:
        return ret


@dataclass
class ToastMessage:
    content: str
    duration: int
    position: Literal["left", "center", "right"]
    color: Literal["info", "error", "warn", "success"]


input_queue: Queue[ToastMessage] = Queue()
queues: List[weakref.ReferenceType[Queue[ToastMessage]]] = []


def emit_message(
        content: str, duration: int = 2,
        position: Literal["left", "center", "right"] = "center",
        color: Literal["info", "error", "warn", "success"] = "info"):
    input_queue.put(ToastMessage(content, duration, position, color))


emit_thread: Thread = None


def start_emit():
    def emitter():
        invalid = []
        while True:
            msg = input_queue.get()
            logger.debug(TAG, f"start_emit queue {queues}")
            for index, ref in enumerate(queues):
                queue = ref()
                if queue is not None and queue.qsize() < 20:
                    queue.put(msg)
                else:
                    invalid.append(index)
            queue = None
            if invalid:
                list(map(queues.pop, reversed(invalid)))
            invalid.clear()
            sleep(.5)
    global emit_thread
    emit_thread = Thread(target=emitter, daemon=True)
    emit_thread.start()

v_thread: Thread = None

def start_v():
    def v():
        while True:
            emit_message(f"{datetime.now().replace(microsecond=0)} | peers {len(queues)}")
            sleep(5)
    global v_thread
    v_thread = Thread(target=v, daemon=True)
    v_thread.start()


if config.logger_level == "VERBOSE":
    start_v()
