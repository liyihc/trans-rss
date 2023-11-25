from datetime import datetime
from typing import Dict, Union

from pydantic import BaseModel


class _SubStatus(BaseModel):
    title: str
    link: str
    torrent: str
    query_time: Union[datetime, None]
    last_error: bool = False


_status: Dict[str, _SubStatus] = {}

_error_msg: str = ""


def status_update(name: str, title: str, link: str, torrent: str):
    _status[name] = _SubStatus(
        title=title, link=link, torrent=torrent,
        query_time=datetime.now().replace(microsecond=0))


def status_error(name: str):
    if name in _status:
        _status[name].query_time = datetime.now().replace(microsecond=0)
        _status[name].last_error = True
    else:
        _status[name] = _SubStatus(
            title="", link="", torrent="",
            query_time=datetime.now().replace(microsecond=0), last_error=True)


def status_get(name: str):
    return _status.get(name, None)


def set_status_error_msg(msg: str):
    global _error_msg
    _error_msg = msg


def get_status_error_msg():
    return _error_msg
