import logging
import logging.handlers
import pathlib


from .config import log_dir

api = log_dir / "interactive"
update = log_dir / "update"
exception = log_dir / "exception"
trans_rss = log_dir / "trans-rss"

for dir in [log_dir, api, update, exception, trans_rss]:
    dir.mkdir(parents=True, exist_ok=True)

fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")


def init_logger(name: str, folder: pathlib.Path):
    logger = logging.getLogger(name)
    handler = logging.handlers.TimedRotatingFileHandler(
        folder / "log", when="midnight", encoding='utf-8')
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger


api_logger = init_logger("api", api)
api_logger.setLevel(logging.INFO)
update_logger = init_logger("update", update)
update_logger.setLevel(logging.INFO)
exception_logger = init_logger("exception", exception)
exception_logger.setLevel(logging.INFO)
trans_rss_logger = init_logger("trans-rss", trans_rss)
trans_rss_logger.setLevel(logging.INFO)
