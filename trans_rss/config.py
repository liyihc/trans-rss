import json
from pathlib import Path
from pydantic import BaseModel
from typing import Optional


version = (Path(__file__).parent / "version").read_text()
class Config(BaseModel):
    transmission_host: str = ""
    port: int = 9091
    username: Optional[str] = None
    password: Optional[str] = None
    subscribe_minutes: int = 60


config_dir = Path(__file__).parents[1] / "configs"

config_path = config_dir / "config.json"
if config_path.exists():
    config = Config.parse_file(config_path)
else:
    config = Config()
config_path.write_text(config.json(indent=4))
sql_path = config_dir / "data.sqlite3"