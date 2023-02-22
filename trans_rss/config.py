from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

import transmission_rpc


version = (Path(__file__).parent / "version").read_text()
class Config(BaseModel):
    transmission_host: str = ""
    protocol: str = "http"
    port: int = 9091
    username: Optional[str] = None
    password: Optional[str] = None
    subscribe_minutes: int = 60
    webhooks: List[str] = []
    timezone:int = 8

    def trans_client(self):
        return transmission_rpc.Client(
            protocol=self.protocol,
            host=self.transmission_host,
            port=self.port,
            username=self.username,
            password=self.password)

    def now(self):
        return datetime.now(timezone(timedelta(hours=self.timezone))).replace(tzinfo=None)



config_dir = Path(__file__).parents[1] / "configs"

if not config_dir.exists():
    config_dir.mkdir()

config_path = config_dir / "config.json"
if config_path.exists():
    config = Config.parse_file(config_path)
else:
    config = Config()
config_path.write_text(config.json(indent=4))
sql_path = config_dir / "data.sqlite3"