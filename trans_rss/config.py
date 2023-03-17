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


class Debug(BaseModel):
    without_transmission: bool = False


class Webhook(BaseModel):
    type: str
    enabled: bool = True
    url: str


CONFIG_VERSION = "config_version"


class Config(BaseModel):
    transmission_host: str = ""
    protocol: str = "http"
    port: int = 9091
    username: Optional[str] = None
    password: Optional[str] = None
    subscribe_minutes: int = 60
    auto_start:bool = True
    webhooks: List[Webhook] = []
    timezone: str = "Asia/Shanghai"
    base_folder: str = "/downloads/complete"
    debug: Debug = Debug()
    config_version: Literal["0.1.0"] = "0.1.0"

    def trans_client(self, timeout=30):
        return transmission_rpc.Client(
            protocol=self.protocol,
            host=self.transmission_host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=timeout)

    def get_seconds(self):
        return self.subscribe_minutes * 60

    def refresh(self):
        self.base_folder = self.base_folder.removesuffix("/")
        self.username = self.username or None
        self.password = self.password or None
        config_path.write_text(self.json(indent=4))
        os.environ["TZ"] = self.timezone
        if system() != "Windows":
            time.tzset()

    def join(self, path: str):
        return f"{self.base_folder}/{path}"


app_dir = Path(__file__).parents[1]
config_dir: Path = app_dir / "configs"
log_dir = app_dir / "logs"
config_path = config_dir / "config.json"
sql_path = config_dir / "data.sqlite3"
webhook_dir = config_dir / "webhooks"
webhook_builtin_dir = Path(__file__).parent / "builtin_webhooks"

config_dir.mkdir(parents=True, exist_ok=True)
webhook_dir.mkdir(parents=True, exist_ok=True)


def update_config(obj: dict):
    ver = obj.get(CONFIG_VERSION, "0.0.0")
    if ver == Config.__fields__[CONFIG_VERSION].get_default():
        return obj
    ver = Version(ver)

    ret = obj.copy()
    for to_ver, updater in updaters:
        if to_ver > ver:
            updater(ret)
    return ret


def update_to_0_1_0(obj: dict):
    webhooks = []
    for url in obj.get("webhooks", []):
        webhooks.append({
            "type": "feishu",
            "url": url
        })
    obj["webhooks"] = webhooks


updaters = [
    (Version("0.1.0"), update_to_0_1_0)
]

if config_path.exists():
    with config_path.open('r') as r:
        obj = json.load(r)
    obj = update_config(obj)
    config = Config.parse_obj(obj)
else:
    config = Config()

config.refresh()
