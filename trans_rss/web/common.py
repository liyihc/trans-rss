import contextvars
from functools import partial, wraps
from typing import Literal
from pywebio import *
import requests
from ..logger import exception_logger
from trans_rss.config import config


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


def catcher(func):
    @wraps(func)
    async def wrapper(*args, **kwds):
        if in_catcher.get():
            return await func(*args, **kwds)
        else:
            try:
                in_catcher.set(True)
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
    try:
        return True, requests.get(url, timeout=3, proxies=config.get_proxies())
    except Exception as e:
        return False, str(e)
