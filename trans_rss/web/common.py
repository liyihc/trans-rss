import asyncio
import contextvars
import weakref
from functools import partial, wraps
from queue import Queue
from typing import Literal

import requests
from pywebio import *

from trans_rss.config import config

from ..common import ToastMessage, input_queue, queues
from ..logger import exception_logger


def generate_header():
    with output.use_scope("header", True):
        from trans_rss.config import get_repeat, set_repeat
        row = [
            output.put_buttons(
                ["订阅列表", "日志", "配置", "API page"],
                onclick=[
                    lambda: session.go_app("sub-list", False),
                    lambda: session.go_app("log", False),
                    lambda: session.go_app("config", False),
                    lambda: session.run_js(
                        'window.open("/docs", "_blank")')
                ]),
            output.put_text("当前状态：")
        ]

        @catcher
        async def set_repeat_refresh(value: bool):
            set_repeat(value)
            generate_header()
        if get_repeat():
            row.append(output.put_text("运行中").style('color: green'))
            row.append(output.put_button("停止", partial(
                set_repeat_refresh, False), "danger"))
        else:
            row.append(output.put_text("未运行").style('color: grey'))
            row.append(output.put_button("开始", partial(
                set_repeat_refresh, True), "success"))
        output.put_row(row, "60% 10% 10% 10%")


in_catcher = contextvars.ContextVar("in_catcher", default=False)


async def loop_listener(queue: Queue[ToastMessage]):
    try:
        while True:
            msg = await asyncio.to_thread(queue.get)
            output.toast(msg.content, msg.duration, msg.position, msg.color)
    except:
        pass


def catcher(func):
    @wraps(func)
    async def wrapper(*args, **kwds):
        if in_catcher.get():
            return await func(*args, **kwds)
        else:
            try:
                queue = Queue()
                queues.append(weakref.ref(queue))
                in_catcher.set(True)
                session.run_async(loop_listener(queue))
                return await func(*args, **kwds)
            except exceptions.SessionException:
                raise
            except Exception as e:
                exception_logger.exception(e, stack_info=True)
                output.toast(f"内部错误：{str(e)}", -1, color="error")
                raise
            finally:
                in_catcher.set(False)

    return wrapper


def button(label, value=None, color: Literal["primary", "secondary", "success", "info", "warn", "danger", "light", "dark"] = "primary", disabled=False):
    return {
        "label": label,
        "value": value,
        "color": color,
        "disabled": disabled
    }


def requests_get(url: str):
    return requests.get(url, timeout=3, headers=config.get_headers(), proxies=config.get_proxies())
