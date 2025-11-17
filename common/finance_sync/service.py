"""财务数据同步服务"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from uuid import uuid4

from common.finance_sync.fetcher import FinanceDataFetcher
from common.persistence import get_session_factory, session_scope, models
from common.persistence.repository import (
    FinanceRecordRepository,
    FinanceSyncLogRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class FinanceRecordPayload:
    """结构化后的财务数据行"""

    record_id: str
    keep_date: date
    type_no: str
    type_name: Optional[str]
    company_no: str
    company_id: Optional[int]
    company_name: Optional[str]
    high_company_no: Optional[str]
    level: Optional[str]
    current_amount: Optional[Decimal]
    last_year_amount: Optional[Decimal]
    last_year_total_amount: Optional[Decimal]
    this_year_total_amount: Optional[Decimal]
    add_amount: Optional[Decimal]
    add_rate: Optional[Decimal]
    year_add_amount: Optional[Decimal]
    year_add_rate: Optional[Decimal]
    raw_payload: Dict[str, Any]


class FinanceDataSyncError(RuntimeError):
    """财务同步异常"""


class FinanceDataSyncService:
    """负责将外部财务数据写入本地数据库"""

    def __init__(
        self,
        *,
        session_factory=None,
        fetcher: Optional[FinanceDataFetcher] = None,
    ) -> None:
        self.session_factory = session_factory or get_session_factory()
        self.fetcher = fetcher or FinanceDataFetcher()

    def sync(self, keep_date: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """执行同步"""

        mode = "single-month" if keep_date else "full"
        records = self.fetcher.fetch(keep_date)
        try:
            payloads = [self._to_payload(item) for item in records]
        except ValueError as exc:  # pragma: no cover - 数据脏值
            raise FinanceDataSyncError(f"解析财务数据失败: {exc}") from exc

        log_id = str(uuid4())
        started_at = datetime.utcnow()

        with session_scope(self.session_factory) as session:
            log_repo = FinanceSyncLogRepository(session)
            log_repo.add(
                models.FinanceSyncLogORM(
                    id=log_id,
                    source="finance_api",
                    mode=mode,
                    status="running",
                    started_at=started_at,
                    fetched_count=len(payloads),
                )
            )

        if dry_run:
            logger.info("Dry run 模式，不写入数据库")
            return {
                "log_id": log_id,
                "fetched": len(payloads),
                "inserted": 0,
                "updated": 0,
                "dry_run": True,
            }

        inserted = 0
        updated = 0

        try:
            with session_scope(self.session_factory) as session:
                record_repo = FinanceRecordRepository(session)
                log_repo = FinanceSyncLogRepository(session)
                log = log_repo.get(log_id)

                for payload in payloads:
                    existing = record_repo.get(payload.record_id)
                    if existing:
                        self._apply_payload(existing, payload)
                        existing.sync_log_id = log_id
                        updated += 1
                    else:
                        record_repo.add(self._payload_to_model(payload, log_id))
                        inserted += 1

                if log:
                    log.status = "success"
                    log.finished_at = datetime.utcnow()
                    log.inserted_count = inserted
                    log.updated_count = updated

            logger.info(
                "财务同步完成 log=%s fetched=%d inserted=%d updated=%d",
                log_id,
                len(payloads),
                inserted,
                updated,
            )
            return {
                "log_id": log_id,
                "fetched": len(payloads),
                "inserted": inserted,
                "updated": updated,
                "dry_run": False,
            }
        except Exception as exc:
            logger.exception("财务同步失败: %s", exc)
            with session_scope(self.session_factory) as session:
                log = FinanceSyncLogRepository(session).get(log_id)
                if log:
                    log.status = "failed"
                    log.error_message = str(exc)
                    log.finished_at = datetime.utcnow()
            raise

    def _to_payload(self, raw: Dict[str, Any]) -> FinanceRecordPayload:
        record_id = raw.get("id")
        if not record_id:
            raise ValueError("记录缺少 id 字段")

        keep_date_value = (raw.get("keepDate") or "").split(" ")[0]
        if not keep_date_value:
            raise ValueError("记录缺少 keepDate 字段")
        try:
            keep_date = datetime.strptime(keep_date_value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"无法解析日期: {keep_date_value}") from exc

        return FinanceRecordPayload(
            record_id=str(record_id),
            keep_date=keep_date,
            type_no=str(raw.get("typeNo")),
            type_name=raw.get("typeName"),
            company_no=str(raw.get("companyNo")),
            company_id=self._to_int(raw.get("companyId")),
            company_name=raw.get("companyName"),
            high_company_no=raw.get("highCompanyNo"),
            level=raw.get("level"),
            current_amount=self._to_decimal(raw.get("currentAmt")),
            last_year_amount=self._to_decimal(raw.get("lastYearAmt")),
            last_year_total_amount=self._to_decimal(raw.get("lastYearTotalAmt")),
            this_year_total_amount=self._to_decimal(raw.get("thisYearTotalAmt")),
            add_amount=self._to_decimal(raw.get("addAmt")),
            add_rate=self._to_decimal(raw.get("addRate")),
            year_add_amount=self._to_decimal(raw.get("yearAddAmt")),
            year_add_rate=self._to_decimal(raw.get("yearAddRate")),
            raw_payload=raw,
        )

    def _payload_to_model(self, payload: FinanceRecordPayload, log_id: Optional[str]) -> models.FinanceRecordORM:
        return models.FinanceRecordORM(
            id=payload.record_id,
            sync_log_id=log_id,
            keep_date=payload.keep_date,
            type_no=payload.type_no,
            type_name=payload.type_name,
            company_no=payload.company_no,
            company_id=payload.company_id,
            company_name=payload.company_name,
            high_company_no=payload.high_company_no,
            level=payload.level,
            current_amount=payload.current_amount,
            last_year_amount=payload.last_year_amount,
            last_year_total_amount=payload.last_year_total_amount,
            this_year_total_amount=payload.this_year_total_amount,
            add_amount=payload.add_amount,
            add_rate=payload.add_rate,
            year_add_amount=payload.year_add_amount,
            year_add_rate=payload.year_add_rate,
            raw_payload=payload.raw_payload,
        )

    def _apply_payload(self, record: models.FinanceRecordORM, payload: FinanceRecordPayload) -> None:
        record.keep_date = payload.keep_date
        record.type_no = payload.type_no
        record.type_name = payload.type_name
        record.company_no = payload.company_no
        record.company_id = payload.company_id
        record.company_name = payload.company_name
        record.high_company_no = payload.high_company_no
        record.level = payload.level
        record.current_amount = payload.current_amount
        record.last_year_amount = payload.last_year_amount
        record.last_year_total_amount = payload.last_year_total_amount
        record.this_year_total_amount = payload.this_year_total_amount
        record.add_amount = payload.add_amount
        record.add_rate = payload.add_rate
        record.year_add_amount = payload.year_add_amount
        record.year_add_rate = payload.year_add_rate
        record.raw_payload = payload.raw_payload

    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        if value in (None, "", "null"):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):  # pragma: no cover - 数据脏值
            logger.warning("无法转换为 Decimal: %s", value)
            return None

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        if value in (None, "", "null"):
            return None
        try:
            return int(value)
        except ValueError:  # pragma: no cover - 数据脏值
            logger.warning("无法转换为 int: %s", value)
            return None
