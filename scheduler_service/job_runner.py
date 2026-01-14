"""执行调度任务的辅助函数。"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

try:  # pragma: no cover - croniter 可选依赖
    from croniter import croniter
except ImportError:  # pragma: no cover
    croniter = None  # type: ignore

from common.persistence.repository import SourceRepository
from common.persistence import models
from crawler_service.config_loader import CrawlerRuntimeConfig
from crawler_service.scheduler import run_crawler_config_with_stats


def _now() -> datetime:
    return datetime.now(timezone.utc)


def calculate_next_run_time(
    job_type: str,
    schedule_cron: Optional[str],
    interval_minutes: Optional[int],
    *,
    enabled: bool = True,
    from_time: Optional[datetime] = None,
) -> Optional[datetime]:
    """根据配置计算下一次运行时间。"""

    if not enabled or job_type != "scheduled":
        return None
    base = from_time or _now()
    if schedule_cron and croniter:
        try:
            itr = croniter(schedule_cron, base)
            return itr.get_next(datetime)
        except (ValueError, KeyError):
            return None
    if schedule_cron and croniter is None:
        return None
    if interval_minutes:
        return base + timedelta(minutes=interval_minutes)
    return None


def calculate_next_run(job: models.CrawlerJobORM, from_time: Optional[datetime] = None) -> Optional[datetime]:
    return calculate_next_run_time(
        job.job_type,
        job.schedule_cron,
        job.interval_minutes,
        enabled=job.enabled,
        from_time=from_time,
    )


def build_runtime_config(
    job: models.CrawlerJobORM,
    payload: Dict[str, Any],
    session: Session,
) -> CrawlerRuntimeConfig:
    """将 job + payload 转成爬虫运行配置。"""

    source_repo = SourceRepository(session)
    source = source_repo.get_by_id(job.source_id)
    if not source:
        source = source_repo.get_or_create_default(
            crawler_name=job.crawler_name,
            category=payload.get("meta", {}).get("category") or "frontier",
            label=job.name or job.crawler_name,
            base_url=f"https://{job.crawler_name}.example.com",
        )
        session.flush()

    meta = payload.get("meta") or {}
    return CrawlerRuntimeConfig(
        source_id=source.id,
        source_name=source.name,
        crawler_name=job.crawler_name,
        meta=meta,
    )


def _write_job_log(log_path: Path, log_lines: List[str]) -> None:
    """将日志写入文件。"""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
    except Exception:
        pass  # 日志写入失败不影响主流程


def _execute_crawler_job(
    job: models.CrawlerJobORM,
    run: models.CrawlerJobRunORM,
    session: Session,
    payload: Dict[str, Any],
) -> int:
    """执行爬虫任务，返回结果数量。"""
    import time

    runtime_config = build_runtime_config(job, payload, session)
    retry_conf = runtime_config.meta.get("retry_config") or job.retry_config or {}
    max_attempts = int(retry_conf.get("max_attempts", 1) or 1)
    attempt_backoff = float(retry_conf.get("attempt_backoff", 1.5) or 1.5)

    # 准备日志
    log_dir = Path("logs") / "scheduler" / job.id
    log_path = log_dir / f"{run.id}.log"
    log_lines: List[str] = []
    log_lines.append(f"任务名称: {job.name}")
    log_lines.append(f"爬虫: {job.crawler_name}")
    log_lines.append(f"来源: {runtime_config.source_name}")
    log_lines.append(f"开始时间: {datetime.now(timezone.utc).isoformat()}")
    log_lines.append(f"最大重试次数: {max_attempts}")
    log_lines.append("-" * 40)

    last_result = None
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        log_lines.append(f"第 {attempts} 次尝试...")

        start_ts = time.time()
        crawl_result = run_crawler_config_with_stats(runtime_config, session)
        duration_ms = int((time.time() - start_ts) * 1000)
        last_result = crawl_result

        stats = crawl_result.stats
        result_count = len(crawl_result.articles)

        # 记录详细统计
        log_lines.append(f"网站爬取: {stats.total_fetched} 条")
        log_lines.append(f"已存在: {crawl_result.duplicates} 条")
        log_lines.append(f"新增派发: {result_count} 条")

        if stats.errors:
            log_lines.append(f"警告/错误:")
            for err in stats.errors[:5]:
                log_lines.append(f"  - {err}")

        run.duration_ms = duration_ms
        run.retry_attempts = attempts
        run.started_at = run.started_at or datetime.now(timezone.utc)
        run.finished_at = datetime.now(timezone.utc)
        run.log_path = str(log_path)

        # 判断状态：如果有错误且爬取数为0，则认为失败
        if stats.has_errors and stats.total_fetched == 0:
            run.error_type = "crawl_error"
            run.error_message = "; ".join(stats.errors[:3])
            log_lines.append(f"状态: failed (爬取失败)")

            if attempts >= max_attempts:
                break
            log_lines.append(f"等待重试...")
            time.sleep(attempt_backoff ** attempts)
            continue
        else:
            # 成功（可能有警告）
            run.error_type = None
            run.error_message = None

            if stats.has_errors:
                log_lines.append(f"状态: success (有警告)")
            else:
                log_lines.append(f"状态: success")

            log_lines.append(f"耗时: {duration_ms}ms")
            log_lines.append("-" * 40)
            log_lines.append(f"结束时间: {datetime.now(timezone.utc).isoformat()}")
            _write_job_log(log_path, log_lines)

            # 更新 result_count 为派发数量
            run.result_count = result_count
            return result_count

    # 最终失败，写入日志
    log_lines.append("-" * 40)
    log_lines.append(f"最终状态: failed (共尝试 {attempts} 次)")
    log_lines.append(f"结束时间: {datetime.now(timezone.utc).isoformat()}")
    _write_job_log(log_path, log_lines)

    # 抛出异常让上层知道失败了
    if last_result and last_result.stats.errors:
        raise Exception("; ".join(last_result.stats.errors[:3]))
    raise Exception("爬取失败：未获取到任何数据")


def _execute_finance_sync(
    job: models.CrawlerJobORM,
    run: models.CrawlerJobRunORM,
    payload: Dict[str, Any],
) -> int:
    """执行财务数据同步任务。"""
    import time
    from formatter_service.worker import task_finance_sync

    log_dir = Path("logs") / "scheduler" / job.id
    log_path = log_dir / f"{run.id}.log"
    log_lines: List[str] = []
    log_lines.append(f"任务名称: {job.name}")
    log_lines.append(f"任务类型: finance_sync")
    log_lines.append(f"开始时间: {datetime.now(timezone.utc).isoformat()}")
    log_lines.append("-" * 40)

    start_ts = time.time()
    try:
        # 从 payload 获取可选参数
        month = payload.get("month")
        dry_run = payload.get("dry_run", False)

        # 直接调用任务函数（同步执行）
        result = task_finance_sync(month=month, dry_run=dry_run)
        duration_ms = int((time.time() - start_ts) * 1000)

        run.duration_ms = duration_ms
        run.finished_at = datetime.now(timezone.utc)
        run.log_path = str(log_path)

        if result.get("status") == "ok":
            log_lines.append(f"同步完成")
            log_lines.append(f"获取记录: {result.get('fetched', 0)}")
            log_lines.append(f"新增记录: {result.get('inserted', 0)}")
            log_lines.append(f"更新记录: {result.get('updated', 0)}")
            log_lines.append(f"状态: success")
            log_lines.append(f"耗时: {duration_ms}ms")
            run.result_count = result.get("fetched", 0)
            run.error_type = None
            run.error_message = None
        else:
            log_lines.append(f"同步失败: {result.get('error', '未知错误')}")
            log_lines.append(f"状态: failed")
            run.error_type = "sync_error"
            run.error_message = result.get("error", "未知错误")
            run.result_count = 0

        log_lines.append("-" * 40)
        log_lines.append(f"结束时间: {datetime.now(timezone.utc).isoformat()}")
        _write_job_log(log_path, log_lines)

        if result.get("status") != "ok":
            raise Exception(result.get("error", "财务同步失败"))

        return run.result_count

    except Exception as exc:
        duration_ms = int((time.time() - start_ts) * 1000)
        run.duration_ms = duration_ms
        run.finished_at = datetime.now(timezone.utc)
        run.log_path = str(log_path)
        run.error_type = "exception"
        run.error_message = str(exc)
        log_lines.append(f"异常: {exc}")
        log_lines.append("-" * 40)
        log_lines.append(f"结束时间: {datetime.now(timezone.utc).isoformat()}")
        _write_job_log(log_path, log_lines)
        raise


def _execute_embeddings_index(
    job: models.CrawlerJobORM,
    run: models.CrawlerJobRunORM,
    payload: Dict[str, Any],
) -> int:
    """执行向量化索引任务。"""
    import time
    from formatter_service.worker import task_embeddings_index

    log_dir = Path("logs") / "scheduler" / job.id
    log_path = log_dir / f"{run.id}.log"
    log_lines: List[str] = []
    log_lines.append(f"任务名称: {job.name}")
    log_lines.append(f"任务类型: embeddings_index")
    log_lines.append(f"开始时间: {datetime.now(timezone.utc).isoformat()}")
    log_lines.append("-" * 40)

    start_ts = time.time()
    try:
        # 从 payload 获取参数
        days = payload.get("days", 2)  # 默认处理最近2天
        force = payload.get("force", False)  # 默认增量模式
        limit = payload.get("limit")
        article_ids = payload.get("article_ids")
        all_articles = payload.get("all_articles", False)

        log_lines.append(f"参数: days={days}, force={force}, limit={limit}")

        # 直接调用任务函数（同步执行）
        result = task_embeddings_index(
            article_ids=article_ids,
            all_articles=all_articles,
            days=days,
            limit=limit,
            force=force,
        )
        duration_ms = int((time.time() - start_ts) * 1000)

        run.duration_ms = duration_ms
        run.finished_at = datetime.now(timezone.utc)
        run.log_path = str(log_path)

        if result.get("status") == "ok":
            log_lines.append(f"向量化完成")
            log_lines.append(f"处理文章数: {result.get('articles', 0)}")
            log_lines.append(f"索引分块数: {result.get('chunks_indexed', 0)}")
            log_lines.append(f"强制模式: {result.get('force', False)}")
            log_lines.append(f"状态: success")
            log_lines.append(f"耗时: {duration_ms}ms")
            run.result_count = result.get("chunks_indexed", 0)
            run.error_type = None
            run.error_message = None
        else:
            log_lines.append(f"向量化失败: {result.get('error', '未知错误')}")
            log_lines.append(f"状态: failed")
            run.error_type = "index_error"
            run.error_message = result.get("error", "未知错误")
            run.result_count = 0

        log_lines.append("-" * 40)
        log_lines.append(f"结束时间: {datetime.now(timezone.utc).isoformat()}")
        _write_job_log(log_path, log_lines)

        if result.get("status") != "ok":
            raise Exception(result.get("error", "向量化失败"))

        return run.result_count

    except Exception as exc:
        duration_ms = int((time.time() - start_ts) * 1000)
        run.duration_ms = duration_ms
        run.finished_at = datetime.now(timezone.utc)
        run.log_path = str(log_path)
        run.error_type = "exception"
        run.error_message = str(exc)
        log_lines.append(f"异常: {exc}")
        log_lines.append("-" * 40)
        log_lines.append(f"结束时间: {datetime.now(timezone.utc).isoformat()}")
        _write_job_log(log_path, log_lines)
        raise


def execute_job_once(
    job: models.CrawlerJobORM,
    run: models.CrawlerJobRunORM,
    session: Session,
) -> int:
    """执行任务一次，根据 task_type 分发到不同执行函数。"""

    payload = dict(job.payload or {})
    payload.update(run.params_snapshot or {})

    task_type = getattr(job, "task_type", "crawler") or "crawler"

    if task_type == "crawler":
        return _execute_crawler_job(job, run, session, payload)
    elif task_type == "finance_sync":
        return _execute_finance_sync(job, run, payload)
    elif task_type == "embeddings_index":
        return _execute_embeddings_index(job, run, payload)
    else:
        raise ValueError(f"未知任务类型: {task_type}")
