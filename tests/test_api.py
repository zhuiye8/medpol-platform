import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api_gateway.main import app
from common.persistence import models
from common.domain import ArticleCategory


@pytest.fixture
def client(db_session, monkeypatch):
    os.environ["DATABASE_URL"] = "sqlite+pysqlite://"

    def _session_factory():
        return lambda: db_session

    monkeypatch.setattr("api_gateway.deps.get_session_factory", lambda: _session_factory())
    monkeypatch.setattr("api_gateway.deps.SessionLocal", None)
    monkeypatch.setattr("api_gateway.deps.get_session_factory_cached", lambda: _session_factory())
    return TestClient(app)


def test_list_articles(client, db_session):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    source = models.SourceORM(
        id="src-demo",
        name="Demo Source",
        label="Demo",
        base_url="https://example.com",
        category=ArticleCategory.FRONTIER,
        is_active=True,
        meta={},
    )
    db_session.add(source)
    article = models.ArticleORM(
        id="art-demo",
        source_id="src-demo",
        title="Demo Title",
        translated_title="Demo 标题",
        content_html="<p>正文</p>",
        content_text="正文",
        publish_time=now,
        source_name="Demo Source",
        source_url="https://example.com/1",
        category=ArticleCategory.FRONTIER,
        status=None,
        tags=["demo"],
        crawl_time=now,
        content_source="web_page",
        summary="摘要",
    )
    db_session.add(article)
    db_session.commit()

    response = client.get("/v1/articles?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert len(data["data"]["items"]) == 1
    item = data["data"]["items"][0]
    assert item["status"] is None
    assert item["translated_title"] == "Demo 标题"


def test_fetch_logs(client, tmp_path, monkeypatch):
    log_file = tmp_path / "runtime.log"
    log_file.write_text("line-a\nline-b\nline-c\n", encoding="utf-8")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))

    response = client.get("/v1/admin/logs?limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["total"] == 3
    assert payload["data"]["lines"][0]["content"] == "line-a"
    assert payload["data"]["lines"][-1]["content"] == "line-c"


def test_create_and_list_scheduler_job(client, db_session):
    source = models.SourceORM(
        id="src-job",
        name="Job Source",
        label="Job",
        base_url="https://example.com",
        category=ArticleCategory.FRONTIER,
        is_active=True,
        meta={"crawler_name": "pharnex_frontier"},
    )
    db_session.add(source)
    db_session.commit()

    payload = {
        "name": "Test Job",
        "crawler_name": "pharnex_frontier",
        "source_id": "src-job",
        "job_type": "scheduled",
        "interval_minutes": 60,
        "payload": {"meta": {"max_pages": 1}},
        "enabled": True,
    }
    response = client.post("/v1/crawler-jobs", json=payload)
    assert response.status_code == 200
    job_id = response.json()["data"]["id"]

    list_resp = client.get("/v1/crawler-jobs")
    assert list_resp.status_code == 200
    assert any(item["id"] == job_id for item in list_resp.json()["data"]["items"])


def test_article_detail(client, db_session):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    source = models.SourceORM(
        id="src-detail",
        name="Detail Source",
        label="Detail",
        base_url="https://example.com",
        category=ArticleCategory.FRONTIER,
        is_active=True,
        meta={},
    )
    db_session.add(source)
    article = models.ArticleORM(
        id="art-detail",
        source_id="src-detail",
        title="Detail Article",
        translated_title="详情标题",
        content_html="<p>原文</p>",
        content_text="原文",
        publish_time=now,
        source_name="Detail Source",
        source_url="https://example.com/1",
        category=ArticleCategory.FRONTIER,
        status=None,
        tags=[],
        crawl_time=now,
        content_source="web_page",
        summary="摘要内容",
        translated_content="翻译正文",
        translated_content_html="<p>翻译正文</p>",
        original_source_language="en",
        ai_analysis={"content": "分析内容", "is_positive_policy": None},
    )
    db_session.add(article)
    ai_result = models.AIResultORM(
        id="ai-1",
        article_id="art-detail",
        task_type="summary",
        provider="mock",
        model="auto",
        output="摘要",
        latency_ms=0,
    )
    db_session.add(ai_result)
    db_session.commit()

    response = client.get("/v1/articles/art-detail")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Detail Article"
    assert data["translated_title"] == "详情标题"
    assert data["translated_content"] == "翻译正文"
    assert data["ai_analysis"]["content"] == "分析内容"
    assert len(data["ai_results"]) == 1
    assert data["ai_results"][0]["task_type"] == "summary"
