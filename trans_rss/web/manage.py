from pywebio import input, output

from .common import catcher
from .. import actions
from ..sql import Connection, Subscribe
from ..config import config


@catcher
async def manage_subscribe(sub: Subscribe):
    table = ["标题 下载链接 下载日期 下载id 下载状态 操作".split()]

    with Connection() as conn:
        if not config.debug.without_transmission:
            trans_client = config.trans_client()
        async for title, url, torrent_url in actions.subscribe(sub):
            row = [
                output.put_link(title, url),
                output.put_link("下载链接", torrent_url)
            ]
            download = conn.download_get(torrent_url)
            if download:
                row.append(
                    output.put_text(str(download.dt))
                )
                if download.id is not None and not config.debug.without_transmission:
                    torrent = trans_client.get_torrent(download.id)
                    row.extend([
                        output.put_text(download.id),
                        output.put_text(torrent.status, torrent.progress),
                        output.put_text()
                    ])
                else:
                    row.extend([
                        output.put_text(),
                        output.put_text(),
                        output.put_text()
                    ])
            else:
                row.extend([
                    output.put_text("-") for _ in range(4)
                ])
            table.append(row)
            with output.use_scope("manage", True):
                output.put_table(table)
