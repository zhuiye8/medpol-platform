"""简单的任务调度脚本，周期性检查 crawler_jobs 并运行。"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from uuid import uuid4

from common.persistence.database import get_session_factory, session_scope
from common.persistence import models
from common.persistence.repository import CrawlerJobRepository
from scheduler_service.job_runner import calculate_next_run, execute_job_once
from crawler_service.scheduler import _load_crawlers


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def process_due_jobs(session) -> int:
    repo = CrawlerJobRepository(session)
    due_jobs = repo.list_due_jobs(utc_now())
    processed = 0

    for job in due_jobs:
        # For non-crawler tasks, use task_type as executed_crawler
        task_type = getattr(job, "task_type", "crawler") or "crawler"
        executed_name = job.crawler_name if task_type == "crawler" else task_type

        run = models.CrawlerJobRunORM(
            id=str(uuid4()),
            job_id=job.id,
            status="running",
            started_at=utc_now(),
            executed_crawler=executed_name or task_type,
            params_snapshot={},
            result_count=0,
            log_path=None,
            error_message=None,
        )
        repo.create_run(run)
        session.flush()
        try:
            count = execute_job_once(job, run, session)
            run.status = "success"
            run.result_count = count
        except Exception as exc:  # pylint: disable=broad-except
            run.status = "failed"
            run.error_message = str(exc)
        finally:
            run.finished_at = utc_now()
            job.last_run_at = run.finished_at
            job.last_status = run.status
            job.next_run_at = calculate_next_run(job, run.finished_at)
            processed += 1
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run crawler job scheduler loop.")
    parser.add_argument("--interval", type=int, default=60, help="轮询间隔（秒）")
    parser.add_argument("--once", action="store_true", help="只运行一次并退出")
    args = parser.parse_args()

    # 加载所有爬虫模块
    _load_crawlers()

    session_factory = get_session_factory()

    while True:
        with session_scope(session_factory) as session:
            processed = process_due_jobs(session)
            session.commit()
        if args.once:
            break
        time.sleep(max(args.interval, 5))


if __name__ == "__main__":
    main()
