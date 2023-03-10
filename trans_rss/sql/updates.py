from sqlite3 import Connection
from packaging.version import Version
from ..logger import trans_rss_logger, exception_logger


def update_to_0_3_0(conn: Connection):
    conn.execute("ALTER TABLE downloaded ADD id INT")
    conn.execute('REPLACE INTO infos VALUES("version", "0.3.0")')


updaters = [
    (Version("0.3.0"), update_to_0_3_0)

]


def update(conn: Connection):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM infos WHERE key='version'")
    version = Version(cursor.fetchone()[0])
    if version >= updaters[-1][0]:
        return
    for to_version, updater in updaters:
        if to_version > version:
            try:
                trans_rss_logger.info(f"update sql from {version} to {to_version}")
                with conn:
                    updater(conn)
            except Exception as e:
                exception_logger.exception(str(e), stack_info=True)
                raise
                

