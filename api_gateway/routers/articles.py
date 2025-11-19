"""文章查询路由，实现统一响应壳。"""

from __future__ import annotations

from datetime import datetime
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
    articles, total = repo.paginate(page=page, page_size=page_size, category=category)

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
            apply_status=a.apply_status,
            is_positive_policy=a.is_positive_policy,
        )
        for a in articles
    ]

    stats: dict | None = None
    if category in {ArticleCategory.FDA_POLICY, ArticleCategory.EMA_POLICY, ArticleCategory.PMDA_POLICY}:
        year = datetime.utcnow().year
        stats = {
            "total_count": repo.count_by_category(category),
            "year_count": repo.count_year_category(category, year),
            "positive_count": repo.count_positive_policy(category),
        }
    elif category == ArticleCategory.PROJECT_APPLY:
        year = datetime.utcnow().year
        stats = repo.count_project_apply_stats(year)

    data = ArticleListData(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        stats=stats,
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
        apply_status=article.apply_status,
        is_positive_policy=article.is_positive_policy,
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


@router.get("/stats/policies", response_model=Envelope[dict])
async def policy_stats(db: Session = Depends(get_db_session)) -> Envelope[dict]:
    """返回 FDA/EMA/PMDA 分类的总数/当年/利好统计。"""

    repo = ArticleRepository(db)
    year = datetime.utcnow().year
    result = {}
    for cat in [ArticleCategory.FDA_POLICY, ArticleCategory.EMA_POLICY, ArticleCategory.PMDA_POLICY]:
        result[cat.value] = {
            "total_count": repo.count_by_category(cat),
            "year_count": repo.count_year_category(cat, year),
            "positive_count": repo.count_positive_policy(cat),
        }
    return Envelope(code=0, msg="success", data=result)


@router.get("/stats/project_apply", response_model=Envelope[dict])
async def project_apply_stats(db: Session = Depends(get_db_session)) -> Envelope[dict]:
    """项目申报统计：未申报/已申报及当年。"""

    repo = ArticleRepository(db)
    year = datetime.utcnow().year
    data = repo.count_project_apply_stats(year)
    return Envelope(code=0, msg="success", data=data)


@router.post("/project_apply/{article_id}/mark_submitted", response_model=Envelope[dict])
async def mark_project_submitted(article_id: str, db: Session = Depends(get_db_session)) -> Envelope[dict]:
    """将项目申报状态标记为已申报。"""

    repo = ArticleRepository(db)
    article = repo.get_by_id(article_id)
    if not article or article.category != ArticleCategory.PROJECT_APPLY:
        raise HTTPException(status_code=404, detail="项目申报文章不存在")
    article.apply_status = "submitted"
    return Envelope(code=0, msg="success", data={"article_id": article_id, "apply_status": "submitted"})
