from pywebio.platform.fastapi import webio_routes

from .subscribe import sub_list_page, subscribe_page
from .logs import log_page
from .config import config_page, webhook_page

routes = webio_routes(
    {
        "index": sub_list_page,
        "sub-list": sub_list_page,
        "subscribe": subscribe_page,
        "log": log_page,
        "config": config_page,
        # "webhook": webhook_page
    }
)
