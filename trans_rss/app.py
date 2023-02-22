from pathlib import Path
import sqlite3
from tkinter import W
from typing import List
from fastapi import FastAPI
import transmission_rpc
import xml
from .config import version, config
from .sql import sql, Subscribe


app = FastAPI(title="Trans RSS", version=version)


@app.get("/")
def hello():
    return "Hello world"


@app.get("/api/test-sql")
def hello(sql_statement: str):
    return sql.fetchall(sql_statement)


@app.post("/api/subscribe")
def subscribe(name: str, url: str):
    sql.subscribe(name, url)


@app.delete("/api/subscribe")
def subscribe(name: str):
    sql.subscribe_del(name)


@app.get("/api/subscribe", response_model=List[Subscribe])
def subscribe():
    return sql.subscribe_get()
