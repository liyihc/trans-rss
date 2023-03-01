from functools import wraps
from traceback import print_exc
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
                # lambda: session.go_app("webhook", False),
                lambda: session.run_js('window.open("/docs", "_blank")')
            ])


def catcher(func):
    @wraps(func)
    async def wrapper(*args, **kwds):
        try:
            await func(*args, **kwds)
        except exceptions.SessionException:
            raise
        except Exception as e:
            print(str(e))
            print_exc()
            exception_logger.exception(e, stack_info=True)
            raise

    return wrapper
