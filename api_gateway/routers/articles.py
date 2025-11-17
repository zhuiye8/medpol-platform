"""文章查询路由，实现统一响应壳。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from common.domain import ArticleCategory
from common.persistence.repository import ArticleRepository, AIResultRepository
from ..deps import get_db_session
from ..schemas import ArticleItem, ArticleListData, Envelope, ArticleDetailData, AIResultItem


router = APIRouter()


@router.get("/", response_model=Envelope[ArticleListData])
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: ArticleCategory | None = Query(None),
    db: Session = Depends(get_db_session),
) -> Envelope[ArticleListData]:
    """查询文章列表，支持简单分页与分类过滤。"""

    repo = ArticleRepository(db)
    articles = repo.list_recent(limit=page_size, category=category)

    items = [
        ArticleItem(
            id=a.id,
            title=a.title,
            summary=a.summary,
            publish_time=a.publish_time,
            source_name=a.source_name,
            category=a.category,
            tags=a.tags,
            source_url=a.source_url,
        )
        for a in articles
    ]

    data = ArticleListData(
        items=items,
        page=page,
        page_size=page_size,
        total=len(items),
    )
    return Envelope(code=0, msg="success", data=data)


@router.get("/{article_id}", response_model=Envelope[ArticleDetailData])
async def get_article_detail(article_id: str, db: Session = Depends(get_db_session)) -> Envelope[ArticleDetailData]:
    repo = ArticleRepository(db)
    article = repo.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    ai_repo = AIResultRepository(db)
    ai_results = ai_repo.list_by_article(article_id)

    data = ArticleDetailData(
        id=article.id,
        title=article.title,
        content_html=article.content_html,
        translated_content=article.translated_content,
        translated_content_html=article.translated_content_html,
        ai_analysis=article.ai_analysis,
        summary=article.summary,
        publish_time=article.publish_time,
        source_name=article.source_name,
        original_source_language=article.original_source_language,
        ai_results=[
            AIResultItem(
                id=result.id,
                task_type=result.task_type,
                provider=result.provider,
                model=result.model,
                output=result.output,
                created_at=result.created_at,
            )
            for result in ai_results
        ],
    )
    return Envelope(code=0, msg="success", data=data)
