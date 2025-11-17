"""格式化工具函数：字段映射与 HTML 清洗。"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup, Comment

from .rules import ALLOWED_ATTRS, ALLOWED_TAGS, FIELD_MAPPING


def extract_path(data: Dict[str, Any], path: list[str]):
    """按照路径从 dict 中取值，若不存在则返回 None。"""

    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def apply_field_mapping(raw_dict: Dict[str, Any]) -> Dict[str, Any]:
    """根据 FIELD_MAPPING 提取字段并填默认值。"""

    result = {}
    for field, rule in FIELD_MAPPING.items():
        value = extract_path(raw_dict, rule["path"])
        if value is None:
            value = rule.get("default")
        result[field] = value
    return result


def clean_html(html: str) -> str:
    """删除 script/style，保留白名单标签，移除多余属性。"""

    soup = BeautifulSoup(html or "", "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for tag in soup.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        allowed_attrs = ALLOWED_ATTRS.get(tag.name, set())
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed_attrs}
    return str(soup)


def normalize_text(text: str) -> str:
    """压缩多余空白，生成纯文本。"""

    normalized = re.sub(r"\s+", " ", text or "").strip()
    return normalized
