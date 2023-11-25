import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from queue import Queue
from traceback import format_exc
from types import NoneType
from typing import Any, AsyncGenerator, Callable, Generator, Iterable, TypeVar


T = TypeVar("T")


@dataclass
class _ThreadFuncError:
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
                "exception in iter_in_thread\n%s", str(e), stack_info=True)
            q.put(_ThreadFuncError(e.args, format_exc()))

    q = Queue()
    # create_task will start the thread
    task = asyncio.create_task(asyncio.to_thread(new_func, q))
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(1) as pool:
        while True:
            result = await loop.run_in_executor(pool, q.get)
            if isinstance(result, (_ThreadFuncError, NoneType)):
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
                f"exception in iter_in_thread\n%s", str(e), stack_info=True)
            return _ThreadFuncError(e.args, format_exc())
    ret = await asyncio.to_thread(new_func)
    if isinstance(ret, _ThreadFuncError):
        raise Exception(*ret.args)
    else:
        return ret
