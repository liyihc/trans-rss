from pathlib import Path
from pywebio import input, session, output, config
from ..logger import update, trans_rss, logger

from .common import generate_header, catcher

TAG = "Web_Logs"

dirs = {
    "更新记录": update,
    "日志": trans_rss
}


@config(title="Trans RSS logs", theme="dark")
@catcher
async def log_page():
    generate_header()
    typ = await input.actions("选择日志类型", list(dirs.keys()))
    session.set_env(title=f"Trans RSS {typ}")
    dir = dirs[typ]
    files = sorted([(f.name, str(f)) for f in dir.glob("log*")], reverse=True)
    index = -1
    for i, (fn, _) in enumerate(files):
        if fn == "log":
            index = i
            break
    if index >= 0:
        files.insert(0, files.pop(index))
    logger.debug(TAG, f"log_page files {files}")
    file = await input.select(
        "选择日志",
        [{
            "label": name,
            "value": f
        } for name, f in files])
    file = Path(file)
    session.set_env(title=f"Trans RSS {typ} {file.name}")
    output.put_text(file.read_text(encoding='utf-8'))
