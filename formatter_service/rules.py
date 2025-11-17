"""格式化阶段的字段映射与清洗规则。"""

FIELD_MAPPING = {
    "summary": {"path": ["metadata", "abstract"], "default": None},
    "tags": {"path": ["metadata", "tags"], "default": []},
    "content_source": {"path": ["metadata", "content_source"], "default": "web_page"},
    "original_source_language": {
        "path": ["metadata", "original_language"],
        "default": None,
    },
}

ALLOWED_TAGS = {
    "p",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "a",
    "span",
    "br",
    "img",
    "blockquote",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
}

ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt"},
}
