from typing import Generator, List, Literal, Tuple, TypeVar, Union
from xml.dom import expatbuilder
from xml.dom.minidom import Element

import pywebio
from pywebio import input, output, session

from .common import catcher
from trans_rss.subscribe_types import Keys, Actions, iter_node, iter_xml, iter_plain


def iter_text(node: Element):
    for child, path in iter_node(node):
        xml = "".join(iter_xml(child)).strip()
        plain = "".join(iter_plain(child)).strip()
        if xml or plain:
            yield "node", path, xml, plain
        for attr, value in child.attributes.items():
            yield "attr", path + [("Attr", attr)], value, value


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
async def test_xml_page():
    xml = await input.textarea()

    node = expatbuilder.parseString(xml, False)
    if len(node.childNodes) == 1:
        node = node.firstChild
    table = ["路径 文本 记作".split()]
    for type, path, xml, plain in iter_text(node):
        if type == "node":
            path = path + [("Plain", None)]
        table.append([
            output.put_text(pretty_path(path)),
            output.put_text(plain),
            ""
        ])

    output.put_table(table)
