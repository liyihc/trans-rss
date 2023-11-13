from sqlite3 import Connection
from packaging.version import Version
from ..logger import logger

TAG = "Sql_Updates"

version = "0.5.11"

def update_to_0_3_0(conn: Connection):
    conn.execute("ALTER TABLE downloaded ADD id INT")


def update_to_0_5_2(conn: Connection):
    cursor = conn.execute("SELECT url, dt, id FROM downloaded")
    downloads = [(download["url"], download["dt"]) for download in cursor]
    conn.execute("DROP TABLE downloaded")
    conn.execute("""
CREATE TABLE downloaded(
    url VARCHAR(256) PRIMARY KEY,
    dt datetime,
    local_torrent VARCHAR(256)) """)
    conn.executemany("INSERT INTO downloaded(url, dt) VALUES(?,?)", downloads)

def update_to_0_5_11(conn: Connection):
    conn.execute("ALTER TABLE subscribe ADD COLUMN include_words TEXT")
    conn.execute("ALTER TABLE subscribe ADD COLUMN exclude_words TEXT")
    conn.execute('UPDATE subscribe SET include_words = "", exclude_words = ""')


updaters = [
    (Version("0.3.0"), update_to_0_3_0),
    (Version("0.5.2"), update_to_0_5_2),
    (Version("0.5.11"), update_to_0_5_11)
]

assert Version(version) == updaters[-1][0]


def update(conn: Connection):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM infos WHERE key='version'")
    version = Version(cursor.fetchone()[0])
    if version >= updaters[-1][0]:
        return
    for to_version, updater in updaters:
        if to_version > version:
            try:
                logger.warn(
                    TAG, f"update sql from {version} to {to_version}")
                with conn:
                    updater(conn)
                    conn.execute(
                        'REPLACE INTO infos VALUES("version",?)', (str(to_version), ))
            except Exception as e:
                logger.exception(TAG, str(e))
                raise
