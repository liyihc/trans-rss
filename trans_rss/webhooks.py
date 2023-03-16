
from functools import cached_property
import json
from pathlib import Path
from typing import Dict

from pydantic import BaseModel, BaseConfig

from .config import webhook_dir, webhook_builtin_dir


class Webhook(BaseModel):
    builtin: bool = True
    body: dict

    @cached_property
    def body_str(self):
        return json.dumps(self.body)

    class Config(BaseConfig):
        keep_untouched = BaseConfig.keep_untouched + (cached_property, )


_webhooks: Dict[str, Webhook] = {}


def init():
    _webhooks.clear()

    def load_from(dir: Path):
        for path in dir.glob("*.json"):
            _try_add_from_file(path)
    load_from(webhook_builtin_dir)
    load_from(webhook_dir)


def format(type: str, title: str, sub: str, torrent: str) -> str:
    return _webhooks.get(type).body_str.format(
        title=title,
        subscribe=sub,
        torrent=torrent)


def get(type: str):
    return _webhooks.get(type)


def _try_add_from_file(file: Path):
    if file.exists():
        _webhooks[file.name.removesuffix(".json")] = Webhook.parse_file(file)


def add(type: str, webhook: Webhook):
    with (webhook_dir / f"{type}.json").open('w') as w:
        json.dump(webhook.dict(), w, ensure_ascii=False, indent=4)
    _webhooks[type] = webhook


def list():
    return _webhooks.keys()


def remove(type: str):
    (webhook_dir / f"{type}.json").unlink(True)
    del _webhooks[type]
    _try_add_from_file(webhook_builtin_dir / f"{type}.json")
