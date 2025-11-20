"""扫描数据库中待处理的文章，并将 AI 任务投递到 Celery 队列。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_processor.batch import enqueue_ai_jobs  # noqa: E402


def main(limit: int | None = None):
    result = enqueue_ai_jobs(limit=limit)
    if (
        result.summary_pending == 0
        and result.translation_pending == 0
        and result.analysis_pending == 0
        and result.title_translation_pending == 0
    ):
        print("暂无待处理的文章")
        return

    print(
        "AI 任务已入队："
        f"摘要 {result.summary_enqueued}/{result.summary_pending}，"
        f"翻译 {result.translation_enqueued}/{result.translation_pending}，"
        f"标题翻译 {result.title_translation_enqueued}/{result.title_translation_pending}，"
        f"分析 {result.analysis_enqueued}/{result.analysis_pending}"
    )


if __name__ == "__main__":
    main()
