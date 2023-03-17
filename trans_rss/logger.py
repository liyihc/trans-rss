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

def config_updated(key: str, old_value: str, new_value: str):
    trans_rss_logger.info(f"config change {key} from {old_value} to {new_value}")

def webhook_noti_success(type: str, url: str, status_code: int):
    api_logger.info(f"webhook notify success {type} {url} {status_code}")

def webhook_noti_failed(type: str, url: str, status_code: int, body: bytes):
    exception_logger.info(
        f"webhook notify failed {type} {url} {status_code} body={body}")

def webhook_del(type: str, url: str, enable: bool):
    trans_rss_logger.info(f"webhook del {type} {url} {enable}")

def webhook_change(old_type: str, old_url: str, old_enable: bool, new_type: str, new_url, new_enable: bool):
    trans_rss_logger.info(f"webhook change {old_type} {old_url} {old_enable} to {new_type} {new_url} {new_enable}")

def webhook_add(type: str, url: str, enable: bool):
    trans_rss_logger.info(f"webhook add {type} {url} {enable}")