"""尝试修复 AI 分析中未结构化的记录。"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.persistence import models  # noqa: E402
from common.persistence.database import get_session_factory, session_scope  # noqa: E402
from ai_processor.analysis_formatter import format_analysis_content  # noqa: E402


def main(limit: int = 50) -> None:
    session_factory = get_session_factory()
    repaired = 0
    with session_scope(session_factory) as session:
        stmt = (
            select(models.ArticleORM)
            .where(models.ArticleORM.ai_analysis.is_not(None))
            .order_by(models.ArticleORM.updated_at.desc())
            .limit(limit)
        )
        articles = list(session.scalars(stmt))
        for article in articles:
            data = article.ai_analysis or {}
            if data.get("structured"):
                continue
            raw = data.get("raw_text")
            if not raw:
                continue
            formatted, structured = format_analysis_content(raw)
            if structured:
                article.ai_analysis = formatted
                repaired += 1
                print(f"[fix] 文章 {article.id} 解析成功")
        if repaired:
            session.commit()
    print(f"[fix] 完成，修复 {repaired} 篇文章")


if __name__ == "__main__":
    arg_limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    main(limit=arg_limit)
