from datetime import datetime
from typing import Dict, Union

from pydantic import BaseModel


class SubStatus(BaseModel):
    title: str
    query_time: Union[datetime, None]
    modify_time: Union[datetime, None] = None


status: Dict[str, SubStatus] = {}


def status_update(name: str, title: str, exist: bool):
    now = datetime.now().replace(microsecond=0)
    if name in status:
        ss = status[name]
        ss.query_time = now
        if not exist:
            ss.query_time = now
    else:
        status[name] = SubStatus(
            title=title,
            query_time=now,
            modify_time=None if exist else now)
