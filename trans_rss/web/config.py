import asyncio
import json
from typing import Any, Dict
import pytz
from pywebio import input, output, session
from tornado.httpclient import AsyncHTTPClient
from ..config import config, Config
from . import common
from .common import catcher


@catcher
async def test_webhooks():
    from ..webhooks import feishu
    client = AsyncHTTPClient()
    for webhook in config.webhooks:
        body = json.dumps(feishu("测试", "webhook", ""))
        succ = False
        msg = ""
        try:
            assert webhook.startswith("http") 
            resp = await client.fetch( # TODO cannot catch...
                webhook, method="POST", headers={'Content-Type': 'application/json'},
                body=body, raise_error=False)
            if 200 <= resp.code <= 299:
                succ = True
            else:
                succ = False
                msg = resp.body.decode()
        except Exception as e:
            msg = str(e)
        if succ:
            output.toast(f"通知成功: {webhook}")
        else:
            output.toast(
                f"通知失败: {webhook}\n{msg}", color="error")


@catcher
async def config_page():
    common.generate_header()

    output.put_buttons(
        [
            {
                "label": "测试通知", "value": None, "color": "secondary"
            }
        ],
        [
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
            value=config.timezone),
        input.input(
            "下载地址", name="base_folder", value=str(config.base_folder),
            help_text="下载地址，各订阅将会在该地址下下载到自己名字的文件夹内"),
        input.textarea("通知webhooks", name="webhooks",
                       value="\n".join(config.webhooks))
    ])
    data["webhooks"] = [webhook for webhook in data["webhooks"].splitlines()
                        if webhook]
    new_config = Config(**data)
    for key in data.keys():
        setattr(config, key, getattr(new_config, key))
    config.refresh()

    output.toast("更新配置成功，正在刷新页面")

    await asyncio.sleep(2)

    session.go_app("config", False)


async def webhook_page():
    common.generate_header()  # need to maintain config version
