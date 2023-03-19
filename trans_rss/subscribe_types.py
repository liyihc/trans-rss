from functools import cached_property
import json
from pathlib import Path
import re
from types import NoneType
from typing import Dict, Generator, List, Literal, Tuple, TypeVar, Union, get_args
from xml.dom.minidom import Element

from pydantic import BaseModel, BaseConfig

from .config import subscribe_dir, subscribe_builtin_dir

Keys = Literal["title", "gui", "torrent", "description"]
Actions = Literal["Node", "Plain", "XML", "Attr"]

T = TypeVar("T")

_list_type = list


def iter_node(node: Element, path: list = []) -> Generator[Tuple[Element, List[Tuple[Actions, str]]], None, None]:
    child: Element
    for child in node.childNodes:
        if child.nodeType != child.TEXT_NODE:
            p = path + [("Node", child.tagName)]
            yield child, p
            yield from iter_node(child, p)


def iter_xml(node: Element) -> Generator[str, None, None]:
    child: Element
    for child in node.childNodes:
        yield child.toxml()


def iter_plain(node: Element) -> Generator[str, None, None]:
    child: Element
    for child in node.childNodes:
        if child.nodeType != child.TEXT_NODE:
            yield from iter_plain(child)
        else:
            yield child.data


def _get_text(node: Element, path: List[Tuple[Actions, Union[str, None]]], default):
    if not path:
        return default
    child: Element
    match path.pop():
        case "Node", tag:
            for child in node.childNodes:
                if child.nodeType != child.TEXT_NODE and child.tagName == tag:
                    return _get_text(child, path, default)
            return default
        case "Attr", attr:
            value = node.attributes.get(attr, None)
            return value.value if value else default
        case "XML", _:
            return "".join(iter_xml(node)).strip()
        case "Plain", _:
            return "".join(iter_plain(node)).strip()


def get_text(node: Element, path: List[Tuple[Actions, Union[str, None]]], default: Union[T, NoneType] = None) -> Union[str, T]:
    return _get_text(node, _list_type(reversed(path)), default)



class SubscribeType(BaseModel):
    builtin: bool = True
    hostname: str = ""
    example_url: str = ""
    paths: Dict[Keys, List[Tuple[Actions, Union[str, None]]]] = {
        "title": [("Node", "title"), ("Plain", None)],
        "gui": [("Node", "guid"), ("Plain", None)],
        "description": [("Node", "description"), ("Plain", None)]
    }

    @cached_property
    def host_name_pattern(self):
        return re.compile(rf"https?://{re.escape(self.hostname)}")

    @cached_property
    def filename(self):
        return f"{self.hostname.replace('.','_')}.json"

    def get_texts(self, node: Element, default="未找到") -> Dict[Keys, str]:
        return {key: self.get_text(node, key, default) for key in get_args(Keys)}

    def get_text(self, node: Element, key: Keys, default="未找到"):
        return get_text(node, self.get_path(key), default)

    def get_path(self, key: Keys):
        return self.paths.get(key, [])

    class Config(BaseConfig):
        keep_untouched = BaseConfig.keep_untouched + (cached_property, )


_subscribe_types: Dict[str, SubscribeType] = {}


def init():
    _subscribe_types.clear()

    def load_from(dir: Path):
        for path in dir.glob("*.json"):
            _try_add_from_file(path)

    load_from(subscribe_builtin_dir)
    load_from(subscribe_dir)


def _try_add_from_file(file: Path):
    if file.exists():
        st = SubscribeType.parse_file(file)
        _subscribe_types[st.hostname] = st


def list():
    return _subscribe_types.keys()


def add(st: SubscribeType):
    with (subscribe_dir / st.filename).open("w", encoding='utf-8') as w:
        json.dump(st.dict(exclude={"filename"}), w, ensure_ascii=False, indent=4)
    _subscribe_types[st.hostname] = st


def get(hostname: str):
    return _subscribe_types.get(hostname)


def remove(hostname: str):
    st = _subscribe_types[hostname]
    assert not st.builtin
    (subscribe_dir / st.filename).unlink(True)
    st = _subscribe_types.pop(hostname)
    _try_add_from_file(subscribe_builtin_dir / st.filename)


init()
