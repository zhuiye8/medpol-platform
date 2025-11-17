"""AI 处理任务：摘要、翻译、分析。"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

from bs4 import BeautifulSoup
from celery import Celery

from common.clients.llm.base import LLMRequest
from common.clients.llm.openai_provider import OpenAIProvider
from common.clients.llm.deepseek_provider import DeepSeekProvider
from common.clients.llm.mock_provider import MockProvider
from common.clients.llm.router import ProviderRouter
from common.persistence.database import get_session_factory, session_scope
from common.persistence.repository import ArticleRepository, AIResultRepository
from common.persistence import models as orm_models
from common.utils.config import get_settings
from .analysis_formatter import format_analysis_content


logger = logging.getLogger("ai_processor.worker")
settings = get_settings()
AI_QUEUE = os.getenv("AI_QUEUE", "ai")
celery_app = Celery(
    "ai_processor",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.task_default_queue = AI_QUEUE

router = ProviderRouter(primary=settings.ai_primary, fallback=settings.ai_fallback)
registered = False
if settings.openai_api_key:
    router.register(
        OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            default_model=settings.openai_model,
        )
    )
    registered = True
if settings.deepseek_api_key:
    router.register(
        DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            default_model=settings.deepseek_model,
        )
    )
    registered = True
if not registered:
    router.register(MockProvider())

SESSION_FACTORY = None
if os.getenv("DATABASE_URL"):
    try:
        SESSION_FACTORY = get_session_factory()
    except Exception as exc:  # pragma: no cover
        print(f"[ai_processor] init session factory failed: {exc}")
        SESSION_FACTORY = None


def _invoke_llm(prompt: str, task_type: str, meta: Optional[dict] = None):
    request = LLMRequest(prompt=prompt, task_type=task_type, meta=meta or {})
    return router.invoke(request)


def _generate_summary(text: str, title: str) -> str:
    prompt = (
        "请用简体中文生成一段 150 字以内的摘要，概述下文的关键信息。\n\n"
        f"标题：{title}\n\n正文（截断）:\n{text[:2000]}"
    )
    response = _invoke_llm(prompt, "summary")
    return response.content.strip()


def _ask_should_translate(text: str) -> bool:
    snippet = text[:1200]
    prompt = (
        "以下文本是否需要翻译成中文才能被中文读者理解？"
        "如果文本主要是中文或无需翻译，请回答 false；否则回答 true。"
        "只输出 true 或 false。\n\n"
        f"文本：\n{snippet}"
    )
    response = _invoke_llm(prompt, "translation_check")
    answer = response.content.strip().lower()
    return answer.startswith("t")


def _translate_html(html: str) -> str:
    prompt = (
        "请将以下 HTML 内容翻译成简体中文。保持所有标签、属性、换行与图片不变，"
        "只翻译可见的文字，输出完整 HTML：\n\n"
        f"{html}"
    )
    response = _invoke_llm(prompt, "translation")
    return response.content.strip()


def _generate_analysis(text: str, title: str) -> Optional[dict]:
    prompt = (
        "请阅读以下政策内容，使用 JSON 格式输出：\n"
        "{\n"
        '  "key_points": ["要点1", "要点2"],\n'
        '  "risks": ["风险1"],\n'
        '  "actions": ["建议1"]\n'
        "}\n"
        "要求：每个数组包含 1-3 条，语言简洁。\n"
        "必须严格输出合法 JSON，不要使用 ``` 包裹，不要附加额外文字。\n\n"
        f"标题：{title}\n正文：{text[:3000]}"
    )
    response = _invoke_llm(prompt, "analysis")
    analysis, structured = format_analysis_content(response.content)
    if not structured:
        logger.warning("AI 分析未能结构化，将保存原文供后续修复")
    return analysis


def run_summary_job(article_id: str) -> Optional[str]:
    if SESSION_FACTORY is None:
        raise RuntimeError("缺少 DATABASE_URL，无法执行 AI 任务")

    with session_scope(SESSION_FACTORY) as session:
        article_repo = ArticleRepository(session)
        ai_repo = AIResultRepository(session)
        article = article_repo.get_by_id(article_id)
        if not article or article.summary:
            return article.summary if article else None
        summary = _generate_summary(article.content_text, article.title)
        ai_repo.add(
            orm_models.AIResultORM(
                id=str(uuid.uuid4()),
                article_id=article.id,
                task_type="summary",
                provider=settings.ai_primary,
                model="auto",
                output=summary,
                latency_ms=0,
            )
        )
        article.summary = summary
        return summary


def run_translation_job(article_id: str) -> Optional[str]:
    if SESSION_FACTORY is None:
        raise RuntimeError("缺少 DATABASE_URL，无法执行 AI 任务")

    with session_scope(SESSION_FACTORY) as session:
        article_repo = ArticleRepository(session)
        ai_repo = AIResultRepository(session)
        article = article_repo.get_by_id(article_id)
        if not article:
            return None
        lang = (article.original_source_language or "unknown").lower()
        if article.translated_content_html:
            return article.translated_content
        should_translate = True
        if lang.startswith("zh"):
            should_translate = False
        elif lang in ("", "unknown"):
            should_translate = _ask_should_translate(article.content_text)
            article.original_source_language = "zh" if not should_translate else "unknown"
        if not should_translate:
            return None

        translated_html = _translate_html(article.content_html)
        translated_text = BeautifulSoup(translated_html, "html.parser").get_text("\n", strip=True)
        article.translated_content_html = translated_html
        article.translated_content = translated_text

        ai_repo.add(
            orm_models.AIResultORM(
                id=str(uuid.uuid4()),
                article_id=article.id,
                task_type="translation",
                provider=settings.ai_primary,
                model="auto",
                output=translated_text[:2000],
                latency_ms=0,
            )
        )
        return translated_text


def run_analysis_job(article_id: str) -> Optional[dict]:
    if SESSION_FACTORY is None:
        raise RuntimeError("缺少 DATABASE_URL，无法执行 AI 任务")

    with session_scope(SESSION_FACTORY) as session:
        article_repo = ArticleRepository(session)
        ai_repo = AIResultRepository(session)
        article = article_repo.get_by_id(article_id)
        if not article or article.ai_analysis:
            return article.ai_analysis if article else None

        analysis = _generate_analysis(article.content_text, article.title)
        if not analysis:
            return None
        article.ai_analysis = analysis
        ai_repo.add(
            orm_models.AIResultORM(
                id=str(uuid.uuid4()),
                article_id=article.id,
                task_type="analysis",
                provider=settings.ai_primary,
                model="auto",
                output=json.dumps(analysis, ensure_ascii=False),
                latency_ms=0,
            )
        )
        return analysis


@celery_app.task(name="ai_processor.process_summary", queue=AI_QUEUE)
def process_summary(article_id: str) -> dict:
    """Celery 任务入口。"""

    summary = run_summary_job(article_id)
    return {"article_id": article_id, "summary": summary}


@celery_app.task(name="ai_processor.process_translation", queue=AI_QUEUE)
def process_translation(article_id: str) -> dict:
    translated = run_translation_job(article_id)
    return {"article_id": article_id, "translated": bool(translated)}


@celery_app.task(name="ai_processor.process_analysis", queue=AI_QUEUE)
def process_analysis(article_id: str) -> dict:
    analysis = run_analysis_job(article_id)
    return {"article_id": article_id, "analysis": analysis}
