import json
import os
from pathlib import Path
from platform import system
import time
from pydantic import BaseModel
from typing import List, Literal, Optional
from packaging.version import Version

import transmission_rpc


version = (Path(__file__).parent / "version").read_text()


class Webhook(BaseModel):
    type: str
    enabled: bool = True
    url: str


CONFIG_VERSION = "config_version"


class Transmission(BaseModel):
    host: str = ""
    protocol: str = "http"
    port: int = 9091
    username: Optional[str] = None
    password: Optional[str] = None
    pause_after_add = False

    def client(self, timeout=30):
        return transmission_rpc.Client(
            protocol=self.protocol,
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=timeout)

LOG_LEVEL = Literal["VERBOSE", "DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]

import logging
logging.addLevelName(5, "VERBOSE")

class Config(BaseModel):
    transmission: Transmission = Transmission()

    subscribe_minutes: int = 60
    auto_start: bool = True
    cdn: bool = True
    webhooks: List[Webhook] = []
    timezone: str = "Asia/Shanghai"
    base_folder: str = "/downloads/complete"
    http_header_agent: str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    http_proxy: str = ""
    notify_failed_update: bool = True
    without_transmission: bool = True
    auto_page: bool = False
    update_logger_level: LOG_LEVEL = "INFO"
    logger_level: LOG_LEVEL = "INFO"
    config_version: str = "0.2.1"


    def get_seconds(self):
        return self.subscribe_minutes * 60

    def refresh(self):
        self.base_folder = self.base_folder.removesuffix("/")
        transmission = self.transmission
        transmission.username = transmission.username or None
        transmission.password = transmission.password or None
        config_path.write_text(self.json(indent=4))
        os.environ["TZ"] = self.timezone
        if system() != "Windows":
            time.tzset()

    def join(self, path: str):
        return f"{self.base_folder}/{path}"

    def get_proxies(self):
        if self.http_proxy:
            return {
                "http": self.http_proxy,
                "https": self.http_proxy
            }
        return {}

    def get_headers(self):
        return {
            "User-Agent": self.http_header_agent
        }


app_dir = Path(__file__).parents[1]
config_dir: Path = app_dir / "configs"
log_dir = app_dir / "logs"
config_path = config_dir / "config.json"
sql_path = config_dir / "data.sqlite3"
webhook_dir = config_dir / "webhooks"
webhook_builtin_dir = Path(__file__).parent / "builtin_webhooks"
subscribe_dir = config_dir / "subscribes"
subscribe_builtin_dir = Path(__file__).parent / "builtin_subscribes"

config_dir.mkdir(parents=True, exist_ok=True)
webhook_dir.mkdir(parents=True, exist_ok=True)
subscribe_dir.mkdir(parents=True, exist_ok=True)


def update_config(obj: dict):
    ver = obj.get(CONFIG_VERSION, "0.0.0")
    if ver == Config.__fields__[CONFIG_VERSION].get_default():
        return obj
    ver = Version(ver)

    ret = obj.copy()
    for to_ver, updater in updaters:
        if to_ver > ver:
            updater(ret)
    ret.pop(CONFIG_VERSION)
    return ret


def update_to_0_1_0(obj: dict):
    webhooks = []
    for url in obj.get("webhooks", []):
        webhooks.append({
            "type": "feishu",
            "url": url
        })
    obj["webhooks"] = webhooks


def update_to_0_1_1(obj: dict):
    obj["without_transmission"] = obj.get(
        "debug", {}).get("without_transmission", True)

def update_to_0_2_0(obj: dict):
    obj["transmission"] = {
        "host": obj.pop("transmission_host"),
        "protocol": obj.pop("protocol"),
        "port": obj.pop("port"),
        "username": obj.pop("username"),
        "password": obj.pop("password")
    }

updaters = [
    (Version("0.1.0"), update_to_0_1_0),
    (Version("0.1.1"), update_to_0_1_1),
    (Version("0.2.0"), update_to_0_2_0)
]

if config_path.exists():
    with config_path.open('r') as r:
        obj = json.load(r)
    obj = update_config(obj)
    config = Config.parse_obj(obj)
else:
    config = Config()
