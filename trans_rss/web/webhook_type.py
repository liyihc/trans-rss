from functools import partial
import json
import re
from .common import button, catcher
from . import common
from trans_rss import logger, webhook_types
from trans_rss.webhook_types import WebhookType
from trans_rss.config import config
import pywebio
from pywebio import input, output, pin, session


@pywebio.config(title="Trans RSS 自定义webhook模板", theme="dark")
@catcher
async def webhook_type_page():
    common.generate_header()

    output.put_markdown("# 自定义webhook")
    await put_webhook_types()

    @catcher
    async def add_webhook():
        if webhook_types.get("new-webhook"):
            output.toast(
                "无法添加具有相同名字的webhook `new-webhook`",
                0, color="error")
        else:
            webhook_types.add(
                "new-webhook", WebhookType(builtin=False, body={}))
            await put_webhook_types()

    output.put_button("添加新webhook", add_webhook)


async def put_webhook_types():
    with output.use_scope("webhook-types", True):
        for index, webhook_type in enumerate(webhook_types.list()):
            put_webhook_type_normal(index, webhook_type)


def put_webhook_type_normal(index: int, webhook_type):
    with output.use_scope(str(index), True):
        webhook = webhook_types.get(webhook_type)
        output.put_row([
            output.put_markdown(
                f"**{webhook_type}**{' (内置)' if webhook.builtin else ''}"),
            None,
            pin.put_textarea(
                name=f"webhook-type-{index}",
                rows=3, readonly=True,
                value=webhook_types.get(webhook_type).template.template),
            None,
            output.put_buttons(
                [
                    {"label": "编辑", "value": "edit", "color": "primary",
                        "disabled": webhook.builtin},
                    {"label": "删除", "value": "delete",
                        "color": "danger", "disabled": webhook.builtin}
                ], partial(webhook_type_action, index, webhook_type)
            )
        ], "50px 10px 60% 10px auto")


@catcher
async def webhook_type_action(index: int, webhook_type: str, action: str):
    match action:
        case "edit":
            put_webhook_type_edit(index, webhook_type)
        case "delete":
            webhook = webhook_types.get(webhook_type)
            if webhook.builtin:
                output.toast(
                    f"webhook模板 {webhook_type} 为内置webhook，你不能将其删除",
                    duration=0, color="warn")
            else:
                used_webhooks = [
                    hook for hook in config.webhooks if hook.type == webhook_type]
                if used_webhooks:
                    used_webhooks = '\n'.join(
                        hook.url for hook in used_webhooks)
                    output.toast(
                        f"webhook模板 {webhook_type} 被以下webhook使用：\n{used_webhooks}",
                        duration=0, color="warn")
                    return

                confirm = await input.actions(
                    f"确定删除webhook模板{webhook_type}吗？",
                    [button("确定", True, "danger"), button("取消", False, "secondary")])
                
                if confirm:
                    logger.webhook_type_del(webhook_type, webhook.body)
                    webhook_types.remove(webhook_type)
                    await put_webhook_types()

NameTemplate = re.compile(r"^[a-zA-Z0-9\-_]*$")


def put_webhook_type_edit(index: int, webhook_type: str):
    with output.use_scope(str(index), True):
        @catcher
        async def confirm(action: str):
            match action:
                case "confirm":
                    new_type = await pin.pin[f"webhook-name-{index}"]
                    if new_type != webhook_type and new_type in webhook_types._webhook_types:
                        output.toast(
                            f"已有名称为{new_type}的webhook模板", -1, color="error")
                        return
                    if not NameTemplate.fullmatch(new_type):
                        output.toast(
                            "名称内仅可含有大小写字母、数字、减号-、下划线_", -1, color="error")
                        return
                    new_body = await pin.pin[f"webhook-type-{index}"]
                    try:
                        new_body = json.loads(new_body)
                    except Exception as e:
                        output.toast("JSON格式错误", -1, color="error")
                        output.toast(str(e), -1, color="error")
                        logger.webhook_type_json_error(webhook_type, new_body)
                        return

                    new_webhook_type = WebhookType(
                        builtin=False,
                        body=new_body
                    )
                    webhook_types.add(new_type, new_webhook_type)
                    if new_type != webhook_type:
                        webhook_types.remove(webhook_type)
                    await put_webhook_types()
                case "reset":
                    put_webhook_type_edit(index, webhook_type)
                case "cancel":
                    put_webhook_type_normal(index, webhook_type)

        output.put_row([
            pin.put_input(f"webhook-name-{index}", value=webhook_type),
            None,
            pin.put_textarea(
                name=f"webhook-type-{index}",
                rows=10,
                code={"mode": "json"},
                value=webhook_types.get(webhook_type).dumps_indent()),
            None,
            output.put_buttons(
                [
                    {"label": "确认", "value": "confirm", "color": "success"},
                    {"label": "重置", "value": "reset", "color": "warning"},
                    {"label": "取消", "value": "cancel", "color": "secondary"}
                ], confirm
            )
        ], "auto 10px 60% 10px auto")
