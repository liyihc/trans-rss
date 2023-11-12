
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Union
from pydantic import BaseModel

from ..config import sql_path, config
from .updates import update


class Subscribe(BaseModel):
    name: str
    url: str
    include_words: str = ""
    exclude_words: str = ""


class DownloadTorrent(BaseModel):
    url: str
    dt: datetime
    local_torrent: Union[str, None]


class _Sql:
    def __init__(self, conn: sqlite3.Connection, exist: bool) -> None:
        conn.row_factory = sqlite3.Row
        self.conn = conn
        if not exist:
            self.build()
        update(conn)

    def build(self):
        with self.conn as conn:
            conn.execute("""
CREATE TABLE infos(
    key VARCHAR(20) PRIMARY KEY,
    value TEXT) """)
            conn.execute("""
CREATE TABLE subscribe(
    name VARCHAR(20) PRIMARY KEY,
    url TEXT,
    include_words TEXT,
    exclude_words TEXT) """)
            conn.execute("""
CREATE TABLE downloaded(
    url VARCHAR(256) PRIMARY KEY,
    dt datetime,
    local_torrent VARCHAR(256)) """)

            conn.execute('INSERT INTO infos VALUES("version", "0.5.11")')
            conn.commit()

    def subscribe(self, sub: Subscribe):
        self.conn.execute(
            "REPLACE INTO subscribe VALUES(?,?,?,?)",
            (sub.name, sub.url, sub.include_words, sub.exclude_words))
        self.conn.commit()

    def subscribe_del(self, name: str):
        self.conn.execute("DELETE FROM subscribe WHERE name = ?", (name, ))
        self.conn.commit()

    def subscribe_list(self):
        cursor = self.conn.execute("SELECT * FROM subscribe")
        for ret in cursor.fetchall():
            yield Subscribe(**ret)

    def subscribe_get(self, name: str):
        cursor = self.conn.execute(
            "SELECT * FROM subscribe WHERE name = ?", (name, ))
        ret = cursor.fetchone()
        return Subscribe(**ret)

    def download_add(self, url: str, local_torrent: Union[str, None] = None):
        self.conn.execute(
            "INSERT INTO downloaded VALUES(?,?,?)",
            (url, str(datetime.now().replace(microsecond=0)), local_torrent))
        self.conn.commit()

    def download_assign(self, url: str, local_torrent: Union[str, None] = None):
        self.conn.execute(
            "UPDATE downloaded SET local_torrent = ? WHERE url = ?", (local_torrent, url))
        self.conn.commit()

    def download_exist(self, url: str):
        cursor = self.conn.execute(
            "SELECT * FROM downloaded WHERE url = ?", (url, ))
        return cursor.fetchone() is not None

    def download_get(self, url: str):
        cursor = self.conn.execute(
            "SELECT url, dt, local_torrent FROM downloaded WHERE url = ?", (url, ))
        row = cursor.fetchone()
        if row:
            return DownloadTorrent(**row)
        return None


@contextmanager
def Connection():
    exist = sql_path.exists()
    with sqlite3.Connection(sql_path, check_same_thread=False) as conn:
        yield _Sql(conn, exist)
