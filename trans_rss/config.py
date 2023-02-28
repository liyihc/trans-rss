import json
import os
from pathlib import Path
from platform import system
import time
from pydantic import BaseModel
from typing import List, Optional

import transmission_rpc


version = (Path(__file__).parent / "version").read_text()


class Debug(BaseModel):
    without_transmission: bool = False


class Config(BaseModel):
    transmission_host: str = ""
    protocol: str = "http"
    port: int = 9091
    username: Optional[str] = None
    password: Optional[str] = None
    subscribe_minutes: int = 60
    webhooks: List[str] = []
    timezone: str = "Asia/Shanghai"
    base_folder: Path = Path("/downloads/complete")
    debug: Debug = Debug()

    def trans_client(self):
        return transmission_rpc.Client(
            protocol=self.protocol,
            host=self.transmission_host,
            port=self.port,
            username=self.username,
            password=self.password)

    def get_seconds(self):
        return self.subscribe_minutes * 60

    def write(self):
        config_path.write_text(self.json(indent=4))



app_dir = Path(__file__).parents[1] 
config_dir: Path = app_dir / "configs"
log_dir = app_dir / "logs"

if not config_dir.exists():
    config_dir.mkdir()

config_path = config_dir / "config.json"
if config_path.exists():
    config = Config.parse_file(config_path)
else:
    config = Config()

os.environ["TZ"] = config.timezone
if system() != "Windows":
    time.tzset()

config.write()
sql_path = config_dir / "data.sqlite3"
