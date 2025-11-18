"""AI 处理任务：摘要、翻译、分析。"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

from bs4 import BeautifulSoup
from celery import Celery

from common.ai.providers import AIProviderError, AIProviderFactory
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

# 统一使用 AIProviderFactory，保持与对话接口一致的 Provider 选择与回退
provider_factory = AIProviderFactory()

SESSION_FACTORY = None
if os.getenv("DATABASE_URL"):
    try:
        SESSION_FACTORY = get_session_factory()
    except Exception as exc:  # pragma: no cover
        print(f"[ai_processor] init session factory failed: {exc}")
        SESSION_FACTORY = None


def _invoke_llm(prompt: str, task_type: str, temperature: float = 0.2) -> str:
    """
    统一的 LLM 调用入口，使用 ProviderFactory（同对话接口），便于配置与回退一致。
    """

    try:
        bundle = provider_factory.get_client()
    except AIProviderError as exc:
        raise RuntimeError(f"AI Provider 初始化失败: {exc}")

    system_prompt = {
        "summary": "你是医药政策内容的中文摘要助手，回答必须简洁、客观、中文输出。",
        "translation_check": "你是语言识别助手，判断文本是否需要翻译为中文，只回答 true 或 false。",
        "translation": "你是精准中文翻译助手，保持 HTML 标签与格式不变，仅翻译可见文字，专业名词保留。",
        "analysis": "你是要点提炼助手，输出规范 JSON，包括 key_points/risks/actions，每项1-3条，中文。",
    }.get(task_type, "你是联环药业的内容处理助手，回答使用中文。")

    response = bundle.client.chat.completions.create(
        model=bundle.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()

def _generate_summary(text: str, title: str) -> str:
    prompt = (
        "Generate a concise Chinese summary within 150 characters.\n\n"
        f"Title: {title}\n\nBody (truncated):\n{text[:2000]}"
    )
    return _invoke_llm(prompt, "summary").strip()



def _ask_should_translate(text: str) -> bool:
    snippet = text[:1200]
    prompt = (
        "Should this text be translated to Chinese for readers to understand? "
        "Answer false if mainly Chinese or no need; otherwise true. "
        "Only output true or false.\n\n"
        f"Text:\n{snippet}"
    )
    answer = _invoke_llm(prompt, "translation_check").strip().lower()
    return answer.startswith("t")



def _translate_html(html: str) -> str:
    prompt = (
        "Translate the following HTML into Simplified Chinese. Keep all tags, attributes, line breaks, and images unchanged; "
        "only translate visible text and output full HTML.\n\n"
        f"{html}"
    )
    return _invoke_llm(prompt, "translation").strip()



def _generate_analysis(text: str, title: str) -> Optional[dict]:
    prompt = (
        "Read the content and output strict JSON: {\"key_points\":[], \"risks\":[], \"actions\":[]} \n"
        "Each array 1-3 concise Chinese items. Do not wrap with backticks, output valid JSON only.\n\n"
        f"Title: {title}\nBody: {text[:3000]}"
    )
    analysis_raw = _invoke_llm(prompt, "analysis")
    analysis, structured = format_analysis_content(analysis_raw)
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
