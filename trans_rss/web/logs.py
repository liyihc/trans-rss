from pathlib import Path
from pywebio import *
from ..logger import exception_logger, log_dir, update, trans_rss, api, exception

from .common import generate_header, catcher


dirs = {
    "更新记录": update,
    "操作记录": trans_rss,
    "API日志": api,
    "错误日志": exception
}


@config(title="Trans RSS logs", theme="dark")
@catcher
async def log_page():
    generate_header()
    typ = await input.actions("选择日志类型", list(dirs.keys()))
    session.set_env(title=f"Trans RSS {typ}")
    dir = dirs[typ]
    file = await input.select(
        "选择日志",
        [{
            "label": f.name,
            "value": str(f)
        } for f in dir.glob("log*")])
    file = Path(file)
    session.set_env(title=f"Trans RSS {typ} {file.name}")
    output.put_text(file.read_text(encoding='utf-8'))
