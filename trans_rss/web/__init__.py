from pywebio.platform.fastapi import webio_routes

from .subscribe import sub_list_page, subscribe_page
from .logs import log_page
from .config import config_page
from .manage import manage_subscribe_page
from .webhook_type import webhook_type_page
from .subscribe_type import subscribe_type_page
from trans_rss.config import config


routes = webio_routes(
    {
        "index": sub_list_page,
        "sub-list": sub_list_page,
        "subscribe": subscribe_page,
        "log": log_page,
        "config": config_page,
        "subscribe-manage": manage_subscribe_page,
        "webhook-type": webhook_type_page,
        "subscribe-type": subscribe_type_page
    }, cdn=True if config.cdn else "static"
)
