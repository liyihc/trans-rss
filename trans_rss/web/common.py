import contextvars
from functools import wraps
from traceback import print_exc
from typing import Sequence
from pywebio import *
from ..logger import exception_logger


def generate_header():
    with output.use_scope("header"):
        output.put_buttons(
            ["订阅列表", "日志", "配置", "API page"],
            onclick=[
                lambda: session.go_app("sub-list", False),
                lambda: session.go_app("log", False),
                lambda: session.go_app("config", False),
                lambda: session.run_js('window.open("/docs", "_blank")')
            ])


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
                print(str(e))
                print_exc()
                exception_logger.exception(e, stack_info=True)
                output.toast(f"内部错误：{str(e)}", -1, color="error")
                raise
            finally:
                in_catcher.set(False)

    return wrapper
