from pathlib import Path
from traceback import print_exc
from pywebio import *
from ..logger import exception_logger, log_dir

from .common import generate_header


async def log_page():
    try:
        session.set_env(title=f"Trans RSS logs")
        generate_header()
        typ = await input.actions("选择日志类型", ["更新记录", "API日志", "错误日志"])
        match typ:
            case "更新记录":
                dir = "update"
            case "API日志":
                dir = "interactive"
            case "错误日志":
                dir = "exception"
        session.set_env(title=f"Trans RSS {typ}")
        dir = log_dir / dir
        file = await input.select(
            "选择日志",
            [{
                "label": f.name,
                "value": str(f)
            } for f in dir.glob("log*")])
        file = Path(file)
        session.set_env(title=f"Trans RSS {typ} {file.name}")
        output.put_text(file.read_text(encoding='utf-8'))

    except exceptions.SessionException:
        raise
    except Exception as e:
        print(str(e))
        print_exc()
        exception_logger.exception(e, stack_info=True)
        raise
