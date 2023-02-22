
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from pydantic import BaseModel

from .config import sql_path, config


class Subscribe(BaseModel):
    name: str
    url: str


class _Sql:
    def __init__(self, conn:sqlite3.Connection, exist:bool) -> None:
        conn.row_factory = sqlite3.Row
        self.conn = conn
        if not exist:
            self.build()

    def build(self):
        with self.conn as conn:
            conn.execute("""
CREATE TABLE infos(
    key VARCHAR(20),
    value TEXT) """)
            conn.execute("""
CREATE TABLE subscribe(
    name VARCHAR(20),
    url TEXT) """)
            conn.execute("""
CREATE TABLE downloaded(
    url VARCHAR(256) PRIMARY KEY,
    dt datetime) """)

            conn.execute('INSERT INTO infos VALUES("version", "0.1.0")')
            conn.commit()

    def subscribe(self, name: str, url: str):
        self.conn.execute("REPLACE INTO subscribe VALUES(?,?)", (name, url))
        self.conn.commit()

    def subscribe_del(self, name: str):
        self.conn.execute("DELETE FROM subscribe WHERE name = ?", (name, ))
        self.conn.commit()

    def subscribe_get(self):
        cursor = self.conn.execute("SELECT * FROM subscribe")
        for ret in cursor.fetchall():
            yield Subscribe(**ret)

    def download_add(self, url: str):
        self.conn.execute(
            "INSERT INTO downloaded VALUES(?,?)",
            (url, str(config.now().replace(microsecond=0))))
        self.conn.commit()

    def download_exist(self, url: str):
        cursor = self.conn.execute("SELECT * FROM downloaded WHERE url = ?", (url, ))
        return cursor.fetchone() is not None


@contextmanager
def Connection():
    exist = sql_path.exists()
    with sqlite3.Connection(sql_path) as conn:
        yield _Sql(conn, exist)