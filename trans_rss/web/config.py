import asyncio
from copy import deepcopy
from functools import partial
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

import pytz
import pywebio
import requests
from pywebio import input, output, pin, session

from trans_rss import webhook_types
from trans_rss import logger
from trans_rss.common import run_in_thread
from trans_rss.sql.sql import Connection
from trans_rss.web.subscribe_type import requests_get

from ..config import Config, Transmission, Webhook, config
from . import common
from .common import button, catcher


@catcher
async def test_transmission():
    try:
        client = config.transmission.client(5)
        torrents = client.get_torrents()
        output.toast(f"Transmission共有{len(torrents)}个种子正在下载")
        if torrents:
            output.toast(f"Transmission下载的某个种子为{torrents[0].name}")
        output.toast(f"Transmission连接成功", color="success")

    except Exception as e:
        output.toast(f"Transmission连接失败 {str(e)}", -1, color='error')


@catcher
async def test_httpproxy():
    url = None
    try:
        with Connection() as conn:
            url = await input.input(
                "请输入需要连接到的网站",
                value="https://nyaa.si/?page=rss",
                datalist=["https://acg.rip/.xml", "https://nyaa.si/?page=rss"] +
                [sub.url for sub in conn.subscribe_list()]
            )
        try:
            resp = await run_in_thread(requests_get, url)
            if 200 <= resp.status_code <= 299:
                output.toast("连接成功", color="success")
        except:
            output.toast(f'无法通过代理"{config.http_proxy}"连接到{url}', color="error")

    except Exception as e:
        output.toast(f'无法通过代理"{config.http_proxy}"连接到{url}', color="error")


@pywebio.config(title="Trans RSS 配置", theme="dark")
@catcher
async def config_page():
    common.generate_header()

    output.put_buttons(
        [
            button("测试Transmission", None, "secondary"),
            button("测试HTTP代理", None, "secondary"),
            button("管理webhooks模板", None, "secondary"),
            button("管理subscribe模板", None, "secondary")
        ],
        [
            test_transmission,
            test_httpproxy,
            partial(session.go_app, "webhook-type"),
            partial(session.go_app, "subscribe-type")
        ]
    )

    output.put_markdown("# Webhooks")
    await generate_webhooks()

    output.put_markdown("# 配置")
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
            wt = webhook_types.get(webhook.type)
            table.append([
                pin.put_select(
                    f"webhook_type_{ind}", webhook_types.list(), value=webhook.type),
                pin.put_checkbox(
                    f"webhook_enable_{ind}", ["enable"], inline=True, value=["enable"] if webhook.enabled else []),
                pin.put_input(f"webhook_url_{ind}", value=webhook.url),
                output.put_buttons(
                    [
                        button("帮助", "help", "secondary",
                               disabled=not wt.help),
                        button("测试", "test", "secondary"),
                        button("删除", "delete", "danger")
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


def webhook_noti(type: str, url: str, body: bytes):
    try:
        resp = requests.post(
            url, headers={"Content-Type": "application/json"}, data=body, timeout=3)
        if 200 <= resp.status_code <= 299:
            logger.webhook_noti_success(type, url, resp.status_code)
            return True, resp.text
        else:
            logger.webhook_noti_failed(type, url, resp.status_code, body)
            return False, resp.text
    except Exception as e:
        return False, str(e)


@catcher
async def webhook_action(index: int, action: str):
    local_webhooks = local_webhooks_get()
    type = await pin.pin[f"webhook_type_{index}"]
    url = await pin.pin[f"webhook_url_{index}"]
    match action:
        case "help":
            output.toast(f"webhook {type} 的说明：{webhook_types.get(type).help}")
        case "test":
            output.toast(f"通知测试：{type} {url}")
            await asyncio.sleep(1)
            body = webhook_types.format(
                type, "测试 webhook 标题", "测试 webhook 订阅", "https://github.com/liyihc/trans-rss")
            try:
                msg = await run_in_thread(partial(webhook_noti, type, url, body))
                output.toast(f"通知成功: {type} {url}\n{msg}", color="success")
            except Exception as e:
                output.toast(f"通知失败: {url}\n{msg}", duration=0, color="error")
        case "delete":
            webhook = local_webhooks.pop(index)
            if url:
                logger.webhook_del(type, url, webhook.enabled)
                output.toast(
                    f"webhook删除{type} {url} {webhook.enabled}（可通过重置还原此删除）")
            await generate_webhooks()


@catcher
async def webhooks_action(action: str):
    local_webhooks = local_webhooks_get()
    match action:
        case "add":
            local_webhooks.append(
                Webhook(type=list(webhook_types.list())[0], enabled=False, url=""))
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
                        output.toast(
                            f"webhook更新，从{webhook.type} {webhook.url} {webhook.enabled}到{type} {url} {enabled}")
                    else:
                        logger.webhook_add(type, url, enabled)
                        output.toast(f"webhook添加{type} {url} {enabled}")
                webhook.type = type
                webhook.enabled = enabled
                webhook.url = url
            config.webhooks = local_webhooks
            config.refresh()


async def wait_update_configs():
    data: Dict[str, Any] = await input.input_group("", [
        input.radio("独立使用", name="without_transmission",
                    options=[{"label": "是", "value": True},
                             {"label": "否", "value": False}],
                    value=config.without_transmission, help_text="若为“是”，则会停止操作transmission。每次启动时会检查与transmission的连接性"),
        input.input(
            "transmission host", name="transmission_host",
            value=config.transmission.host),
        input.select(
            "transmission 协议", ["http", "https"], name="transmission_protocol",
            value=config.transmission.protocol),
        input.input(
            "transmission 端口", input.NUMBER, name="transmission_port", value=config.transmission.port),
        input.input(
            "transmission 用户名", name="transmission_username", value=config.transmission.username),
        input.input(
            "transmission 密码", input.PASSWORD, name="transmission_password",
            value=config.transmission.password),
        input.input(
            "轮询时间（分钟）", input.NUMBER, name="subscribe_minutes",
            value=config.subscribe_minutes
        ),
        input.radio("自动翻页", name="auto_page",
                    options=[{"label": "是", "value": True},
                             {"label": "否", "value": False}],
                    value=config.auto_page, help_text="不同种子站的翻页规则不一致，之后会添加不同站的翻页支持"),
        input.input(
            "时区", datalist=pytz.all_timezones, name="timezone",
            value=config.timezone, validate=lambda v: None if v in pytz.all_timezones else "时区错误"),
        input.input(
            "下载地址", name="base_folder", value=str(config.base_folder),
            help_text="下载地址，各订阅将会在该地址下下载到自己名字的文件夹内"),
        input.input(
            "HTTP代理", name="http_proxy", value=config.http_proxy,
            help_text="格式为：http://user:pass@123.123.123.123:7890 或 http://123.123.123.132:7890"
        ),
        input.input(
            "HTTP User Agent", name="http_header_agent", value=config.http_header_agent,
            help_text="在浏览器上按F12，选择“网络”后，刷新本页面，选择任意一个连接，即可在消息头中找到User-Agent"
        ),
        input.radio(
            "使用CDN", name="cdn", options=[{"label": "是", "value": True}, {"label": "否", "value": False}],
            value=config.cdn, help_text="否将使用内置CDN，在jsdelivr无法访问时使用。需要重新启动服务才能生效")
    ])

    prefix = "transmission_"
    sub_data = {key.removeprefix(prefix): data.pop(
        key) for key in list(data.keys()) if key.startswith(prefix)}
    sub_data["username"] = sub_data["username"] or None
    sub_data["password"] = sub_data["password"] or None
    data["transmission"] = sub_data


    new_config = Config(**data)

    def update_diff(config: BaseModel, new_config: BaseModel, data: dict, prefix: str=""):
        for key in data.keys():
            value = getattr(config, key)
            new_value = getattr(new_config, key)
            if isinstance(value, BaseModel):
                if prefix:
                    new_prefix = f"{prefix}.{key}."
                else:
                    new_prefix = f"{key}."
                update_diff(value, new_value, data[key], new_prefix)
            elif value != new_value:
                logger.config_updated(key, value, new_value)
                output.toast(f'更新配置{prefix}{key}从"{value}"至"{new_value}"')
                setattr(config, key, new_value)
    update_diff(config, new_config, data)
    config.refresh()

    output.toast("更新配置成功，正在刷新页面", color="success")

    await asyncio.sleep(2)

    session.go_app("config", False)
