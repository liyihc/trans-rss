from datetime import datetime
from typing import Dict, Union

from pydantic import BaseModel


class SubStatus(BaseModel):
    title: str
    url: str
    # gui_url: str # TODO
    query_time: Union[datetime, None]


status: Dict[str, SubStatus] = {}


def status_update(name: str, title: str, url: str, exist: bool):
    now = datetime.now().replace(microsecond=0)
    if name in status:
        ss = status[name]
        ss.query_time = now
    else:
        status[name] = SubStatus(
            title=title, url=url, query_time=now)
