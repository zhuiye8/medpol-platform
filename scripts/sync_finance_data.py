"""财务数据同步脚本"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from common.finance_sync.fetcher import FinanceDataFetcherError
from common.finance_sync.service import FinanceDataSyncError, FinanceDataSyncService

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")


def parse_month(value: str) -> str:
    """接受 YYYY-MM 或 YYYY-MM-DD，统一返回 YYYY-MM-DD"""

    value = value.strip()
    if len(value) == 7:
        value = f"{value}-01"
    datetime.strptime(value, "%Y-%m-%d")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 financeDate/dataList 至本地数据库")
    parser.add_argument("--month", help="仅同步某个月份，格式 YYYY-MM 或 YYYY-MM-DD", default=None)
    parser.add_argument("--dry-run", action="store_true", help="只拉取数据不写入数据库")
    args = parser.parse_args()

    keep_date = parse_month(args.month) if args.month else None

    service = FinanceDataSyncService()
    try:
        stats = service.sync(keep_date=keep_date, dry_run=args.dry_run)
    except (FinanceDataFetcherError, FinanceDataSyncError, ValueError) as exc:
        logging.error("财务数据同步失败: %s", exc)
        sys.exit(1)

    logging.info(
        "同步完成 log_id=%s fetched=%d inserted=%d updated=%d dry_run=%s",
        stats.get("log_id"),
        stats.get("fetched"),
        stats.get("inserted"),
        stats.get("updated"),
        stats.get("dry_run"),
    )


if __name__ == "__main__":
    main()
