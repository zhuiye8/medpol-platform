from datetime import datetime

from formatter_service.worker import process_raw_article
from formatter_service.utils import clean_html
from common.domain import ArticleCategory


def build_raw_payload(**overrides):
    payload = {
        "article_id": "test-1",
        "source_id": "src-test",
        "source_name": "测试来源",
        "category": ArticleCategory.FRONTIER.value,
        "title": "示例标题",
        "content_html": "<div><p>内容</p><script>alert(1)</script></div>",
        "source_url": "https://example.com/article/1",
        "publish_time": datetime.utcnow().isoformat(),
        "crawl_time": datetime.utcnow().isoformat(),
        "content_source": "web_page",
        "metadata": {
            "abstract": "摘要信息",
            "tags": ["tag1", "tag2"],
            "original_language": "zh",
            "content_source": "web_page",
        },
    }
    payload.update(overrides)
    return payload


def test_process_raw_article_mapping_and_cleaning():
    payload = build_raw_payload()
    result = process_raw_article(payload)
    assert result["skipped"] is False
    article = result["article"]
    assert article["summary"] == "摘要信息"
    assert article["tags"] == ["tag1", "tag2"]
    assert "<script>" not in article["content_html"]


def test_process_raw_article_missing_title_skipped():
    payload = build_raw_payload(title="")
    result = process_raw_article(payload)
    assert result["skipped"] is True
    assert result["reason"] == "missing_required_field"


def test_clean_html_removes_disallowed_tags():
    html = "<div><span>keep</span><script>bad</script><iframe src='x'></iframe></div>"
    cleaned = clean_html(html)
    assert "script" not in cleaned
    assert "iframe" not in cleaned
    assert "<span>keep</span>" in cleaned
