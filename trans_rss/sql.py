
from pathlib import Path
import sqlite3
from pydantic import BaseModel

from .config import sql_path


class Subscribe(BaseModel):
    name: str
    url: str


class Sql:
    def __init__(self) -> None:
        self.open_or_build()

    def open_or_build(self):
        if sql_path.exists():
            return
        with sqlite3.Connection(sql_path) as conn:
            conn.execute("""
CREATE TABLE infos(
    key VARCHAR(20),
    value TEXT) """)
            conn.execute("""
CREATE TABLE subscribe(
    name VARCHAR(20),
    url TEXT) """)

            conn.execute('INSERT INTO infos VALUES("version", "0.1.0")')

    def execute(self, sql_statement: str, param):
        with sqlite3.Connection(sql_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(sql_statement, param)
            conn.commit()

    def fetchall(self, sql_statement: str):
        with sqlite3.Connection(sql_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql_statement)
            return cursor.fetchall()

    def subscribe(self, name: str, url: str):
        self.execute("REPLACE INTO subscribe VALUES(?,?)", (name, url))

    def subscribe_del(self, name: str):
        self.execute("DELETE FROM subscribe WHERE name = ?", (name, ))

    def subscribe_get(self):
        for ret in self.fetchall("SELECT * FROM subscribe"):
            yield Subscribe(**ret)


sql = Sql()
