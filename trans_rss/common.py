from datetime import datetime
from typing import Dict, Union

from pydantic import BaseModel


class SubStatus(BaseModel):
    title: str
    link: str
    torrent: str
    query_time: Union[datetime, None]


status: Dict[str, SubStatus] = {}


def status_update(name: str, title: str, link: str, torrent: str):
    status[name] = SubStatus(
        title=title, link=link, torrent=torrent,
        query_time=datetime.now().replace(microsecond=0))
