"""从数据库或默认配置运行所有爬虫。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler_service.scheduler import run_active_crawlers  # noqa: E402
from common.persistence.database import get_session_factory, session_scope  # noqa: E402
from common.utils.env import load_env  # noqa: E402


def main():
    load_env()
    total = 0
    if os.getenv("DATABASE_URL"):
        session_factory = get_session_factory()
        with session_scope(session_factory) as session:
            total = run_active_crawlers(session=session)
    else:
        total = run_active_crawlers()
    print(f"✅ 完成采集，共 {total} 条")


if __name__ == "__main__":
    main()
