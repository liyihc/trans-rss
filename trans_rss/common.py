import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from traceback import format_exc
from types import NoneType
from typing import Any, AsyncGenerator, Callable, Dict, Generator, Iterable, TypeVar, Union
import logging

from pydantic import BaseModel


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
        status[name] = SubStatus(title="", link="", torrent="", query_time=datetime.now().replace(microsecond=0), last_error=True)
    
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
            return True, func(*args, **kwds)
        except Exception as e:
            logger = logging.getLogger("exception")
            logger.exception(
                f"exception in iter_in_thread\n{str(e)}", stack_info=True)
            return False, str(e)
    return await asyncio.to_thread(new_func)
