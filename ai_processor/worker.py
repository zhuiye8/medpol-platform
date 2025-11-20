"""AI processor: 摘要、正文翻译、标题翻译、联环视角分析的 Celery 任务。"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from bs4 import BeautifulSoup
from celery import Celery

from common.ai.providers import AIProviderError, AIProviderFactory
from common.utils.env import load_env
from common.persistence.database import get_session_factory, session_scope
from common.persistence.repository import ArticleRepository, AIResultRepository
from common.persistence import models as orm_models
from common.utils.config import get_settings
from common.domain import ArticleCategory
from formatter_service.language import detect_language
from .analysis_formatter import format_analysis_content


load_env()
logger = logging.getLogger("ai_processor.worker")
settings = get_settings()

AI_QUEUE = os.getenv("AI_QUEUE", "ai")
celery_app = Celery(
    "ai_processor",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.task_default_queue = AI_QUEUE

# 统一使用 AIProviderFactory，便于动态选择 Provider
provider_factory = AIProviderFactory()

SESSION_FACTORY = None
if os.getenv("DATABASE_URL"):
    try:
        SESSION_FACTORY = get_session_factory()
    except Exception as exc:  # pragma: no cover
        print(f"[ai_processor] init session factory failed: {exc}")
        SESSION_FACTORY = None

_JIESHAO = ""
try:
    _JIESHAO = Path("jieshao.md").read_text(encoding="utf-8", errors="ignore")
except Exception:
    _JIESHAO = ""

POLICY_CATEGORIES = {
    ArticleCategory.FDA_POLICY,
    ArticleCategory.EMA_POLICY,
    ArticleCategory.PMDA_POLICY,
    ArticleCategory.LAWS,
    ArticleCategory.INSTITUTION,
    ArticleCategory.BIDDING,
    ArticleCategory.CDE_TREND,
}


def _base_context() -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    intro = f"当前日期：{today}。你是一名联环生物医药数据助手，回答需专业、精炼。"
    if _JIESHAO:
        intro += "\n联环介绍：" + _JIESHAO[:800]
    return intro


def _invoke_llm(prompt: str, task_type: str, temperature: float = 0.2) -> str:
    """调用 LLM 的通用封装。"""

    try:
        bundle = provider_factory.get_client()
    except AIProviderError as exc:
        raise RuntimeError(f"AI Provider 初始化失败: {exc}")

    response = bundle.client.chat.completions.create(
        model=bundle.model,
        messages=[
            {"role": "system", "content": prompt},
        ],
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


def _summary_prompt(title: str, text: str) -> str:
    return (
        _base_context()
        + "\n请基于医药政策/行业内容生成不超过 150 字的中文摘要，突出要点与结论。\n"
        f"标题: {title}\n正文片段:\n{text[:2000]}"
    )


def _translation_check_prompt(text: str) -> str:
    return (
        _base_context()
        + "\n判断以下文本是否需要翻译成中文阅读。不需要翻译返回 false，需要翻译返回 true。只回答 true 或 false。\n\n"
        f"文本片段：\n{text[:1200]}"
    )


def _translate_html_prompt(html: str) -> str:
    return (
        _base_context()
        + "\n将下面的 HTML 翻译成中文，保持标签结构与排版，保留图片/链接，输出 HTML。"
        "不要添加解释或额外句子，只返回翻译后的 HTML。\n\n"
        f"{html}"
    )


def _translate_title_prompt(title: str) -> str:
    return (
        _base_context()
        + "\n请将以下标题翻译成中文，只返回翻译后的标题，不要添加前后缀、标点或解释。\n\n"
        f"{title}"
    )


def _analysis_prompt(category: ArticleCategory, title: str, text: str) -> str:
    base = _base_context()
    if category in {ArticleCategory.FDA_POLICY, ArticleCategory.EMA_POLICY, ArticleCategory.PMDA_POLICY}:
        angle = "关注监管要求、通道与豁免，对中国企业出海注册/临床的影响，指出利好或风险。"
    elif category in {ArticleCategory.LAWS, ArticleCategory.INSTITUTION, ArticleCategory.CDE_TREND}:
        angle = "关注国内监管/制度变化，对注册、临床、合规、药审效率的影响，给出操作要点。"
    elif category == ArticleCategory.BIDDING:
        angle = "关注集采/招标节奏、价格与准入影响、供应链动作，提示机会与风险。"
    elif category == ArticleCategory.INDUSTRY_TREND:
        angle = "关注行业动态与商业化信号，对管线、合作、市场的启示。"
    elif category == ArticleCategory.PROJECT_APPLY:
        angle = "关注申报条件、材料要求、时间节点与奖励/风险，指出关键动作。"
    else:
        angle = "从业务影响和可执行动作角度给出分析。"
    return (
        base
        + '\n请输出 JSON：{"content":"从联环视角给出的分析","is_positive_policy":true/false/null}。'
        "content 必须直接给出结论和行动建议，不要添加前缀或客套。\n"
        "is_positive_policy 仅在政策/招采/制度类别填写布尔，其余用 null。\n"
        f"分类: {category.value}\n标题: {title}\n正文: {text[:3000]}\n分析侧重：{angle}"
    )


def _parse_analysis(raw: str) -> Tuple[Optional[dict], Optional[bool]]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and ("content" in data or "is_positive_policy" in data):
            return {
                "content": data.get("content"),
                "is_positive_policy": data.get("is_positive_policy"),
            }, data.get("is_positive_policy")
    except Exception:
        pass
    formatted, structured = format_analysis_content(raw)
    is_positive = None
    if isinstance(formatted, dict):
        is_positive = formatted.get("is_positive_policy")
    return formatted if structured else {"content": raw, "is_positive_policy": None}, is_positive


def _generate_summary(text: str, title: str) -> str:
    prompt = _summary_prompt(title, text)
    return _invoke_llm(prompt, "summary").strip()


def _ask_should_translate(text: str) -> bool:
    prompt = _translation_check_prompt(text)
    answer = _invoke_llm(prompt, "translation_check").strip().lower()
    return answer.startswith("t")


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    return len(cjk_chars) / max(len(text), 1)


def _should_translate_text(text: str) -> Tuple[bool, str]:
    """
    规则优先的翻译判定：(need_translate, detected_lang)
    - 明显中文/CJK 占比高，直接不翻译
    - 明显英文/日韩/欧陆语言或 ASCII 占比高，直接翻译
    - 其余交给小模型判定一次
    """
    if not text or len(text.strip()) < 20:
        return False, "unknown"
    lang = (detect_language(text) or "unknown").lower()
    if lang.startswith("zh"):
        return False, "zh"
    if _cjk_ratio(text) >= 0.3:
        return False, "zh"
    ascii_ratio = sum(ch.isascii() for ch in text) / max(len(text), 1)
    if lang in {"en", "ja", "ko", "fr", "de", "es"} or ascii_ratio > 0.7:
        return True, lang
    need_translate = _ask_should_translate(text)
    return need_translate, ("und" if need_translate else "zh")


def _translate_html(html: str) -> str:
    prompt = _translate_html_prompt(html)
    return _invoke_llm(prompt, "translation").strip()


def _translate_title(title: str) -> str:
    prompt = _translate_title_prompt(title)
    return _invoke_llm(prompt, "title_translation").strip()


def _generate_analysis(text: str, title: str, category: ArticleCategory) -> Optional[dict]:
    prompt = _analysis_prompt(category, title, text)
    analysis_raw = _invoke_llm(prompt, "analysis")
    analysis, _ = _parse_analysis(analysis_raw)
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
        lang = (article.original_source_language or "").lower()
        if article.translated_content_html:
            return article.translated_content
        should_translate = True
        if lang.startswith("zh"):
            should_translate = False
        elif lang in ("", "unknown", "und"):
            should_translate, detected_lang = _should_translate_text(article.content_text)
            article.original_source_language = detected_lang
        else:
            should_translate = True
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


def run_title_translation_job(article_id: str) -> Optional[str]:
    if SESSION_FACTORY is None:
        raise RuntimeError("缺少 DATABASE_URL，无法执行 AI 任务")

    with session_scope(SESSION_FACTORY) as session:
        article_repo = ArticleRepository(session)
        ai_repo = AIResultRepository(session)
        article = article_repo.get_by_id(article_id)
        if not article or article.translated_title:
            return article.translated_title if article else None
        lang = (article.original_source_language or "").lower()
        if lang.startswith("zh"):
            article.translated_title = article.title
            ai_repo.add(
                orm_models.AIResultORM(
                    id=str(uuid.uuid4()),
                    article_id=article.id,
                    task_type="title_translation",
                    provider=settings.ai_primary,
                    model="auto",
                    output=article.title,
                    latency_ms=0,
                )
            )
            return article.title
        if lang in ("", "unknown", "und"):
            need_translate, detected_lang = _should_translate_text(article.title or article.content_text)
            article.original_source_language = detected_lang
            if not need_translate:
                article.translated_title = article.title
                return article.title
        translated_title = _translate_title(article.title)
        article.translated_title = translated_title
        ai_repo.add(
            orm_models.AIResultORM(
                id=str(uuid.uuid4()),
                article_id=article.id,
                task_type="title_translation",
                provider=settings.ai_primary,
                model="auto",
                output=translated_title,
                latency_ms=0,
            )
        )
        return translated_title


def run_analysis_job(article_id: str) -> Optional[dict]:
    if SESSION_FACTORY is None:
        raise RuntimeError("缺少 DATABASE_URL，无法执行 AI 任务")

    with session_scope(SESSION_FACTORY) as session:
        article_repo = ArticleRepository(session)
        ai_repo = AIResultRepository(session)
        article = article_repo.get_by_id(article_id)
        if not article or article.ai_analysis:
            return article.ai_analysis if article else None

        analysis = _generate_analysis(article.content_text, article.title, article.category)
        if not analysis:
            return None
        article.ai_analysis = analysis

        is_positive = analysis.get("is_positive_policy") if isinstance(analysis, dict) else None
        if article.category in POLICY_CATEGORIES and isinstance(is_positive, bool):
            article.is_positive_policy = is_positive
        else:
            article.is_positive_policy = None
        logger.info(
            "[analysis] article=%s category=%s is_positive_policy=%s",
            article.id,
            article.category,
            article.is_positive_policy,
        )

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
    """Celery task: generate summary."""

    summary = run_summary_job(article_id)
    return {"article_id": article_id, "summary": summary}


@celery_app.task(name="ai_processor.process_translation", queue=AI_QUEUE)
def process_translation(article_id: str) -> dict:
    """Celery task: translate body."""

    translated = run_translation_job(article_id)
    return {"article_id": article_id, "translated": bool(translated)}


@celery_app.task(name="ai_processor.process_title_translation", queue=AI_QUEUE)
def process_title_translation(article_id: str) -> dict:
    """Celery task: translate title only."""

    translated = run_title_translation_job(article_id)
    return {"article_id": article_id, "translated_title": translated}


@celery_app.task(name="ai_processor.process_analysis", queue=AI_QUEUE)
def process_analysis(article_id: str) -> dict:
    """Celery task: analysis."""

    analysis = run_analysis_job(article_id)
    return {"article_id": article_id, "analysis": analysis}
