import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from queue import Queue
from typing import Any, AsyncGenerator, Callable, Dict, Generator, TypeVar, Union
import logging

from pydantic import BaseModel


class SubStatus(BaseModel):
    title: str
    link: str
    torrent: str
    query_time: Union[datetime, None]


status: Dict[str, SubStatus] = {}


def status_update(name: str, title: str, link: str, torrent: str):
    status[name] = SubStatus(
        title=title, link=link, torrent=torrent,
        query_time=datetime.now().replace(microsecond=0))


T = TypeVar("T")


async def iter_in_thread(func: Callable[..., Generator[T, Any, Any]], *args, **kwds) -> AsyncGenerator[T, Any]:
    def new_func(q: Queue):
        try:
            for item in func(*args, **kwds):
                q.put(item)
        except Exception as e:
            logger = logging.getLogger("exception")
            logger.exception(
                f"exception in iter_in_thread\n{str(e)}", stack_info=True)
        finally:
            q.put(None)

    q = Queue()
    # create_task will start the thread
    task = asyncio.create_task(asyncio.to_thread(new_func, q))
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(1) as pool:
        while True:
            result = await loop.run_in_executor(pool, q.get)
            if result is not None:
                yield result
            else:
                await task  # wait until the task finish
                return


async def run_in_thread(func: Callable[..., T], *args, **kwds) -> T:
    def new_func():
        try:
            return func(*args, **kwds)
        except Exception as e:
            logger = logging.getLogger("exception")
            logger.exception(
                f"exception in iter_in_thread\n{str(e)}", stack_info=True)
    return await asyncio.to_thread(new_func)
