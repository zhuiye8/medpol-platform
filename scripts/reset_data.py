"""一键清空业务数据和本地缓存的脚本。"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from common.persistence.database import get_engine

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - redis 如未安装仅提示
    redis = None


DEFAULT_DIRS = [
    Path("sample_data/outbox"),
    Path("sample_data/normalized"),
    Path("sample_data/cache"),
    Path("sample_data/webhook"),
]
DEDUP_STATE = Path("sample_data/state/formatter_seen.json")

TABLES = [
    "ai_results",
    "articles",
    "crawler_job_runs",
    "crawler_jobs",
    "sources",
]


class ResetResult:
    """一次数据清理任务的统计结果。"""

    def __init__(self) -> None:
        self.truncated_tables: list[str] = []
        self.cleared_dirs: list[str] = []
        self.dedupe_reset: bool = False
        self.redis_cleared: bool = False


def _clean_directory(path: Path) -> None:
    """删除目录下所有文件，但保留目录本身。"""

    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink(missing_ok=True)
        elif item.is_dir():
            shutil.rmtree(item, ignore_errors=True)


def _drop_deduper_state(path: Path) -> None:
    """删除格式化去重状态文件。"""

    if path.exists():
        path.unlink(missing_ok=True)


def _truncate_tables(engine_url: str) -> list[str]:
    """清空核心业务表。"""

    engine = get_engine(engine_url)
    stmt = text(
        "TRUNCATE TABLE "
        + ", ".join(TABLES)
        + " RESTART IDENTITY CASCADE"
    )
    with engine.begin() as conn:
        conn.execute(stmt)
    return TABLES.copy()


def _flush_redis(url: str) -> bool:
    """清空 Redis（存在则执行，不存在跳过）。"""

    if redis is None:
        print("[reset] 未安装 redis 库，跳过 Redis 清理")
        return False

    try:
        client = redis.Redis.from_url(url)
        client.flushdb()
        return True
    except Exception as exc:  # pragma: no cover - Redis 连接失败仅提示
        print(f"[reset] Redis 清理失败：{exc}")
        return False


def reset_all(database_url: str, redis_url: str, extra_dirs: Iterable[Path]) -> ResetResult:
    """清空数据库、本地缓存及 Redis。"""

    result = ResetResult()

    print("[reset] 清空数据库表...")
    result.truncated_tables = _truncate_tables(database_url)

    print("[reset] 清理本地缓存目录...")
    for dir_path in extra_dirs:
        _clean_directory(dir_path)
        result.cleared_dirs.append(str(dir_path))

    print("[reset] 移除去重状态...")
    _drop_deduper_state(DEDUP_STATE)
    result.dedupe_reset = True

    print("[reset] 清理 Redis...")
    result.redis_cleared = _flush_redis(redis_url)

    print("[reset] 已完成所有清理步骤")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="一键清空业务数据脚本")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="数据库连接字符串，默认读取环境变量 DATABASE_URL",
    )
    parser.add_argument(
        "--redis-url",
        default=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        help="Redis 连接字符串，默认读取环境变量 REDIS_URL",
    )
    parser.add_argument(
        "--dir",
        action="append",
        dest="dirs",
        default=[],
        help="额外需要清理的目录，可重复传入",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise RuntimeError("缺少 DATABASE_URL，请通过环境变量或参数传入")

    dirs = DEFAULT_DIRS + [Path(d) for d in args.dirs]
    result = reset_all(args.database_url, args.redis_url, dirs)
    print(
        "[reset] 结果: truncated=%s, dirs=%s, redis=%s"
        % (",".join(result.truncated_tables), len(result.cleared_dirs), result.redis_cleared)
    )


if __name__ == "__main__":
    main()
