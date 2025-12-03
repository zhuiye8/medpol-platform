"""
轻量日志清理脚本，默认清理 logs/ 下超过保留天数的日志文件。

用法示例（PowerShell）：
    python scripts/cleanup_logs.py --path logs --days 14
    python scripts/cleanup_logs.py --path logs/crawler --days 7 --dry-run

注意：
- 不存在的目录会被跳过。
- 仅删除文件，默认会尝试删除已空目录。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理过期日志文件")
    parser.add_argument(
        "--path",
        dest="paths",
        action="append",
        default=["logs"],
        help="需要清理的目录，默认为 logs（可重复传入多次）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="保留天数，早于此天数的文件会被删除，默认 14",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印将要删除的文件，不实际删除",
    )
    parser.add_argument(
        "--keep-empty",
        action="store_true",
        help="保留空目录（默认会删除清理后剩余的空目录）",
    )
    return parser.parse_args()


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for root in paths:
        if not root.exists():
            continue
        for entry in root.rglob("*"):
            if entry.is_file():
                yield entry


def _remove_empty_dirs(root: Path) -> Tuple[int, int]:
    removed_dirs = 0
    errors = 0
    if not root.exists():
        return removed_dirs, errors
    # 自底向上删除空目录
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
                removed_dirs += 1
            except OSError:
                # 非空或被占用，跳过
                continue
            except Exception:
                errors += 1
    return removed_dirs, errors


def cleanup(paths: Iterable[str], retain_days: int, dry_run: bool, keep_empty: bool) -> None:
    now = datetime.now()
    cutoff = now - timedelta(days=retain_days)
    path_objs = [Path(p) for p in paths]

    deleted_files = 0
    deleted_bytes = 0
    skipped = 0

    for file_path in _iter_files(path_objs):
        try:
            stat = file_path.stat()
        except FileNotFoundError:
            continue
        mtime = datetime.fromtimestamp(stat.st_mtime)
        if mtime >= cutoff:
            skipped += 1
            continue
        if dry_run:
            print(f"[DRY-RUN] would delete {file_path} ({stat.st_size} bytes)")
            deleted_files += 1
            deleted_bytes += stat.st_size
            continue
        try:
            file_path.unlink()
            deleted_files += 1
            deleted_bytes += stat.st_size
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[WARN] failed to delete {file_path}: {exc}", file=sys.stderr)
            continue

    removed_dirs_total = 0
    remove_errors = 0
    if not keep_empty:
        for root in path_objs:
            dirs_removed, errors = _remove_empty_dirs(root)
            removed_dirs_total += dirs_removed
            remove_errors += errors

    human_mb = deleted_bytes / (1024 * 1024) if deleted_bytes else 0
    print(
        f"cleaned: files={deleted_files} ({human_mb:.2f} MB), "
        f"skipped={skipped}, dirs_removed={removed_dirs_total}, "
        f"errors={remove_errors}"
    )


def main() -> None:
    args = parse_args()
    cleanup(args.paths, args.days, args.dry_run, args.keep_empty)


if __name__ == "__main__":
    main()
