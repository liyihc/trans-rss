import asyncio
from copy import deepcopy
from functools import partial
from typing import Any, Dict, List

import pytz
import pywebio
import requests
from pywebio import input, output, pin, session
from tornado.httpclient import AsyncHTTPClient

from trans_rss import webhooks
from trans_rss.logger import exception_logger, trans_rss_logger, api_logger
from trans_rss import logger

from ..config import Config, Webhook, config
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


@pywebio.config(title="Trans RSS 配置", theme="dark")
@catcher
async def config_page():
    common.generate_header()

    output.put_buttons(
        [
            {"label": "测试Transmission", "value": None, "color": "secondary"},
            {"label": "管理webhooks模板", "value": None, "color": "secondary"}
        ],
        [
            test_transmission,
            test_transmission,
        ]
    )

    await generate_webhooks()

    await wait_update_configs()


def local_webhooks_get() -> List[Webhook]:
    local_webhooks = session.local.config_webhooks
    if local_webhooks is None:
        local_webhooks = session.local.config_webhooks = deepcopy(
            config.webhooks)
    return local_webhooks


def local_webhooks_reset():
    session.local.config_webhooks = deepcopy(config.webhooks)


async def generate_webhooks():
    local_webhooks = local_webhooks_get()
    with output.use_scope("webhook", clear=True):
        table = ["类型 启用 链接 操作".split()]
        for ind, webhook in enumerate(local_webhooks):
            table.append([
                pin.put_select(
                    f"webhook_type_{ind}", webhooks.list(), value=webhook.type),
                pin.put_checkbox(
                    f"webhook_enable_{ind}", ["enable"], inline=True, value=["enable"] if webhook.enabled else []),
                pin.put_input(f"webhook_url_{ind}", value=webhook.url),
                output.put_buttons(
                    [
                        {"label": "测试", "value": "test", "color": "secondary"},
                        {"label": "删除", "value": "delete", "color": "danger"}
                    ], partial(webhook_action, ind)

                )
            ])
        table.append([
            "", "", "",
            output.put_buttons([
                {"label": "添加", "value": "add", "color": "primary"},
                {"label": "重置", "value": "reset", "color": "warning"},
                {"label": "应用", "value": "apply", "color": "success"}
            ], onclick=webhooks_action)])
        output.put_table(table)


@catcher
async def webhook_action(index: int, action: str):
    local_webhooks = local_webhooks_get()
    type = await pin.pin[f"webhook_type_{index}"]
    url = await pin.pin[f"webhook_url_{index}"]
    match action:
        case "test":
            output.toast(f"通知测试：{type} {url}")
            await asyncio.sleep(1)
            body = webhooks.format(
                type, "测试 webhook 标题", "测试 webhook 订阅", "https://github.com/liyihc/trans-rss")
            succ = False
            msg = ""
            try:
                resp = requests.post(
                    url, headers={"Content-Type": "application/json"},
                    data=body, timeout=3)
                if 200 <= resp.status_code <= 299:
                    succ = True
                else:
                    succ = False
                msg = resp.text
            except Exception as e:
                msg = str(e)
            if succ:
                logger.webhook_noti_success(type, url, resp.status_code)
                output.toast(f"通知成功: {type} {url}\n{msg}", color="success")
            else:
                try:
                    code = resp.status_code
                except:
                    code = 0
                logger.webhook_noti_failed(type, url, code, body)
                output.toast(f"通知失败: {url}\n{msg}", duration=0, color="error")
        case "delete":
            webhook = local_webhooks.pop(index)
            if url:
                logger.webhook_del(type, url, webhook.enabled)
                output.toast(f"webhook删除{type} {url} {webhook.enabled}（可通过重置还原此删除）")
            await generate_webhooks()


@catcher
async def webhooks_action(action: str):
    local_webhooks = local_webhooks_get()
    match action:
        case "add":
            local_webhooks.append(
                Webhook(type=list(webhooks.list())[0], enabled=False, url=""))
            await generate_webhooks()
        case "reset":
            local_webhooks_reset()
            await generate_webhooks()
        case "apply":
            for index, webhook in enumerate(local_webhooks):
                type = await pin.pin[f"webhook_type_{index}"]
                enabled = bool(await pin.pin[f"webhook_enable_{index}"])
                url = await pin.pin[f"webhook_url_{index}"]
                if webhook.type != type or webhook.url != url or webhook.enabled != enabled:
                    if webhook.url:
                        logger.webhook_change(
                            webhook.type, webhook.url, webhook.enabled,
                            type, url, enabled)
                        output.toast(f"webhook更新，从{webhook.type} {webhook.url} {webhook.enabled}到{type} {url} {enabled}")
                    else:
                        logger.webhook_add(type, url, enabled)
                        output.toast(f"webhook添加{type} {url} {enabled}")
                webhook.type = type
                webhook.enabled = enabled
                webhook.url = url
            config.webhooks = local_webhooks
            config.refresh()


async def wait_update_configs():
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
            help_text="下载地址，各订阅将会在该地址下下载到自己名字的文件夹内")
    ])
    new_config = Config(**data)
    for key in data.keys():
        old_value = getattr(config, key)
        new_value = getattr(new_config, key)
        if old_value != new_value:
            logger.config_updated(key, old_value, new_value)
            setattr(config, key, new_value)
    config.refresh()

    output.toast("更新配置成功，正在刷新页面", color="success")

    await asyncio.sleep(2)

    session.go_app("config", False)
