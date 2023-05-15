import asyncio
from copy import deepcopy
from functools import partial
from typing import Generator, Iterable, List, Literal, Tuple, TypeVar, Union
import typing
from urllib.parse import urlparse
from xml.dom import expatbuilder
from xml.dom.minidom import Element

import pywebio
from pywebio import input, output, session, pin

from trans_rss import subscribe_types
from trans_rss import logger
from trans_rss.common import run_in_thread

from .common import button, catcher, requests_get
from . import common
from trans_rss.subscribe_types import Keys, Actions, SubscribeType, iter_node, iter_xml, iter_plain


def iter_text(node: Element):
    for child, path in iter_node(node):
        plain = "".join(iter_plain(child)).strip()
        if plain:
            yield "node", path + [("Plain", None)], plain
        for attr, value in child.attributes.items():
            yield "attr", path + [("Attr", attr)], value


def _pretty_path(path: List[Tuple[Actions, Union[str, None]]]):
    for p in path:
        match p:
            case "Node", tag:
                yield f">{tag}"
            case "Attr", attr:
                yield f"|attr:{attr}"
            case "XML", _:
                yield f"|xml"
            case "Plain", _:
                yield f"|plain"


def pretty_path(path: List[Tuple[Actions, Union[str, None]]]) -> str:
    return "".join(_pretty_path(path))


@pywebio.config(title="测试", theme="dark")
@catcher
async def subscribe_type_page():
    common.generate_header()
    await put_main()


async def put_main():
    with output.use_scope("subscribe-type", True):
        output.put_markdown("# 自定义订阅")
        table = ["网址 键 路径 操作".split()]
        keys = typing.get_args(Keys)
        for hostname in subscribe_types.list():
            subscribe_type = subscribe_types.get(hostname)
            table.append([
                output.span(
                    f"{hostname}{'（内置）' if subscribe_type.builtin else ''}",
                    row=len(keys)
                ),
                keys[0],
                pretty_path(subscribe_type.paths.get(keys[0], [])),
                output.span(output.put_buttons(
                    [
                        {"label": "编辑", "value": "edit", "color": "secondary",
                            "disabled": subscribe_type.builtin},
                        {"label": "删除", "value": "delete", "color": "danger",
                            "disabled": subscribe_type.builtin},
                    ], partial(subscribe_type_action, hostname)
                ), row=len(keys))
            ])
            for key in keys[1:]:
                table.append([
                    key,
                    pretty_path(subscribe_type.paths.get(key, []))
                ])
        output.put_table(table)

        output.put_markdown("**从一个订阅链接添加**")
        pin.put_input("type-add", help_text="为某个特定番剧的订阅，Trans RSS会自动从中提取主网址的")

        @catcher
        async def confirm():
            new_subscribe: str = await pin.pin["type-add"]
            new_subscribe = new_subscribe.strip()
            if not new_subscribe:
                output.toast("选项不能为空", -1, color="warn")
            hostname: str = urlparse(new_subscribe).hostname
            st = subscribe_types.get(hostname)
            if st:
                if not st.builtin:
                    output.toast(f'网址{hostname}已存在', -1, color="danger")
                    return
                else:
                    output.toast(f'覆盖内置网址{hostname}', color="warn")
            logger.subscribe_type("add", hostname)
            subscribe_types.add(SubscribeType(
                builtin=False,
                hostname=hostname,
                example_url=new_subscribe))
            await put_main()
        output.put_button("确认", confirm)


@catcher
async def subscribe_type_action(hostname: str, action: str):
    match action:
        case "edit":
            await put_edit_subscribe_type(hostname)
        case "delete":
            confirm = await input.actions(
                f"确定删除订阅模板{hostname}吗？",
                [
                    button("确定", True, "danger"),
                    button("取消", False, "secondary")
                ])
            if confirm:
                logger.subscribe_type("delete", hostname,
                                      subscribe_types.get(hostname).json())
                subscribe_types.remove(hostname)
                await put_main()


@catcher
async def put_edit_subscribe_type(hostname: str):
    with output.use_scope("subscribe-type", True):
        output.put_markdown(f"# 编辑订阅：{hostname}")
        subscribe_type = subscribe_types.get(hostname)
        table = ["键 路径".split()]
        keys = typing.get_args(Keys)
        for key in keys:
            table.append([
                key,
                pretty_path(subscribe_type.paths.get(key, []))
            ])

        output.put_table(table)

        pin.put_input("example-url", label="测试URL",
                      value=subscribe_type.example_url)

        @catcher
        async def put_edit():
            with output.use_scope("output", True):
                url: str = await pin.pin["example-url"]
                url = url.strip()
                try:
                    resp = await run_in_thread(partial(requests_get, url))
                except:
                    output.toast(f"无法获取网页 {url} {resp}", color="error")
                    return
                doml = expatbuilder.parseString(resp.text, False)
                doml: Element
                item = doml.getElementsByTagName("item")[0]

                output.put_markdown(
                    f"## 原XML\n\n```xml\n{item.toxml()}\n```\n## 配置")

                table = ["路径 文本 记作".split()]
                paths = list(iter_text(item))
                options = ("",) + keys
                for index, (type, path, plain) in enumerate(paths):
                    value = ""
                    for k, p in subscribe_type.paths.items():
                        if p == path:
                            value = k
                    table.append([
                        output.put_text(pretty_path(path)),
                        output.put_text(plain),
                        pin.put_select(
                            f"subscribe-path-{index}", options, value=value)
                    ])

                output.put_table(table)

            await input.actions("", [button("确认", True)])

            new_sub_type = deepcopy(subscribe_type)
            for index, (type, path, plain) in enumerate(paths):
                select = await pin.pin[f"subscribe-path-{index}"]
                if select:
                    new_sub_type.paths[select] = path

            with output.use_scope("output", True):
                output.put_markdown("## 确认测试结果")
                put_table_for_test([item], new_sub_type)

            await input.actions("", [button("确认", True)])

            logger.subscribe_type("modify", hostname, new_sub_type.json())
            subscribe_types.add(new_sub_type)
            await put_edit_subscribe_type(hostname)
            output.clear_scope("output")

        @catcher
        async def put_test():
            with output.use_scope("output", True):
                url = await pin.pin["example-url"]
                try:
                    resp = await run_in_thread(partial(requests_get, url))
                except:
                    output.toast(f"无法获取网页 {url} {resp}", color="error")
                    return
                doml = expatbuilder.parseString(resp.text, False)
                doml: Element
                put_table_for_test(
                    doml.getElementsByTagName("item"), subscribe_type)

        output.put_buttons(
            ["编辑", "测试"],
            [put_edit, put_test]
        )

        return


def put_table_for_test(items: Iterable[Element], sub_type: SubscribeType):
    keys = typing.get_args(Keys)
    table = ["键 值 XML".split()]
    for item in items:
        table.append([
            keys[0],
            sub_type.get_text(item, keys[0]),
            output.span(output.put_markdown(
                f"```xml\n{item.toxml()}\n```"), row=len(keys))
        ])
        for key in keys[1:]:
            table.append(
                [key, sub_type.get_text(item, key)])
    output.put_table(table)
