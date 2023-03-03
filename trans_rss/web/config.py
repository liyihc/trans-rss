import asyncio
import json
from typing import Any, Dict

import pytz
import pywebio
from pywebio import input, output, session
from tornado.httpclient import AsyncHTTPClient
import requests

from ..config import Config, config
from . import common
from .common import catcher


@catcher
async def test_transmission():
    try:
        client = config.trans_client(5)
        torrents = client.get_torrents()
        output.toast(f"Transmission共有{len(torrents)}个种子正在下载")
        if torrents:
            output.toast(f"Transmission下载的某个种子为{torrents[0].name}")
        output.toast(f"Transmission连接成功", color="success")

    except Exception as e:
        output.toast(f"Transmission连接失败 {str(e)}", -1, color='error')


@catcher
async def test_webhooks():
    from ..webhooks import feishu
    # client = AsyncHTTPClient()
    for webhook in config.webhooks:
        output.toast(f"通知测试：{webhook}")
        await asyncio.sleep(1)
        body = json.dumps(feishu("测试", "webhook", ""))
        succ = False
        msg = ""
        try:
            # resp = await session.run_asyncio_coroutine(client.fetch( # TODO cannot catch...
            #     webhook, method="POST", headers={'Content-Type': 'application/json'},
            #     body=body, raise_error=False))
            resp = requests.post(webhook, data=body, timeout=3)
            # if 200 <= resp.code <= 299:
            if 200 <= resp.status_code <= 299:
                succ = True
            else:
                succ = False
            # msg = resp.body.decode()
            msg = resp.text
        except Exception as e:
            msg = str(e)
        if succ:
            output.toast(f"通知成功: {webhook}\n{msg}", color="success")
        else:
            output.toast(
                f"通知失败: {webhook}\n{msg}", duration=0, color="error")


@pywebio.config(title="Trans RSS 配置", theme="dark")
@catcher
async def config_page():
    common.generate_header()

    output.put_buttons(
        [
            {
                "label": "测试Transmission", "value": None, "color": "secondary",
            },
            {
                "label": "测试通知", "value": None, "color": "secondary"
            }
        ],
        [
            test_transmission,
            test_webhooks
        ]
    )

    data: Dict[str, Any] = await input.input_group("配置", [
        input.input(
            "transmission host", name="transmission_host",
            value=config.transmission_host),
        input.select(
            "协议", ["http", "https"], name="protocol",
            value=config.protocol),
        input.input(
            "端口", input.NUMBER, name="port", value=config.port),
        input.input(
            "用户名", name="username", value=config.username),
        input.input(
            "密码", input.PASSWORD, name="password",
            value=config.password),
        input.input(
            "轮询时间（分钟）", input.NUMBER, name="subscribe_minutes",
            value=config.subscribe_minutes
        ),
        input.input(
            "时区", datalist=pytz.all_timezones, name="timezone",
            value=config.timezone, validate=lambda v: None if v in pytz.all_timezones else "时区错误"),
        input.input(
            "下载地址", name="base_folder", value=str(config.base_folder),
            help_text="下载地址，各订阅将会在该地址下下载到自己名字的文件夹内"),
        input.textarea("通知webhooks", name="webhooks",
                       value="\n".join(config.webhooks),
                       help_text="目前仅支持飞书webhook，在保存后，可使用上面的按钮进行测试。无效的webhook会导致订阅服务中指")
    ])
    data["webhooks"] = [webhook for webhook in data["webhooks"].splitlines()
                        if webhook]
    new_config = Config(**data)
    for key in data.keys():
        setattr(config, key, getattr(new_config, key))
    config.refresh()

    output.toast("更新配置成功，正在刷新页面", color="success")

    await asyncio.sleep(2)

    session.go_app("config", False)
