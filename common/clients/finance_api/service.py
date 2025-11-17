"""本地财务数据服务"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import extract, select

from common.persistence import get_session_factory, session_scope, models

logger = logging.getLogger(__name__)


@dataclass
class FinanceRecordDTO:
    """用于工具输出的财务记录"""

    company_no: str
    company_name: Optional[str]
    level: Optional[str]
    keep_date: date
    type_no: str
    type_name: Optional[str]
    metrics: Dict[str, Optional[float]]


def _decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


class FinanceDataService:
    """读取 finance_records 表的服务"""

    def __init__(self, *, session_factory=None) -> None:
        self.session_factory = session_factory or get_session_factory()

    def query_finance_data(
        self,
        finance_type: str,
        keep_date: str,
        company_numbers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        target_date = self._normalize_month(keep_date)
        with session_scope(self.session_factory) as session:
            stmt = select(models.FinanceRecordORM).where(
                models.FinanceRecordORM.type_no == finance_type,
                models.FinanceRecordORM.keep_date == target_date,
            )
            if company_numbers:
                stmt = stmt.where(models.FinanceRecordORM.company_no.in_(company_numbers))
            stmt = stmt.order_by(models.FinanceRecordORM.company_no.asc())
            records = list(session.scalars(stmt))

        items = [self._to_dto(record) for record in records]
        summary = self._summarize(items)
        logger.info(
            "本地财务查询: type=%s month=%s companies=%s 命中=%d",
            finance_type,
            keep_date,
            company_numbers or "all",
            len(items),
        )
        return {
            "query": {
                "finance_type": finance_type,
                "keep_date": target_date.isoformat(),
                "company_numbers": company_numbers or [],
            },
            "results": [self._dto_to_dict(item) for item in items],
            "summary": summary,
        }

    def compare_finance_data(
        self,
        compare_dimension: str,
        finance_type: str,
        company_numbers: List[str],
        years: List[str],
        months: List[str],
    ) -> Dict[str, Any]:
        years_int = [int(y) for y in years]
        months_int = [int(m) for m in months]

        with session_scope(self.session_factory) as session:
            stmt = select(models.FinanceRecordORM).where(
                models.FinanceRecordORM.type_no == finance_type,
                models.FinanceRecordORM.company_no.in_(company_numbers),
                extract("year", models.FinanceRecordORM.keep_date).in_(years_int),
                extract("month", models.FinanceRecordORM.keep_date).in_(months_int),
            )
            records = list(session.scalars(stmt))

        grouped: Dict[str, Dict[str, Any]] = {}
        for record in records:
            dto = self._to_dto(record)
            key, label = self._group_key(compare_dimension, dto)
            bucket = grouped.setdefault(
                key,
                {
                    "label": label,
                    "metrics": self._empty_metrics(),
                    "records": [],
                },
            )
            self._merge_metrics(bucket["metrics"], dto.metrics)
            bucket["records"].append(self._dto_to_dict(dto))

        details = [
            {"key": key, **value}
            for key, value in sorted(grouped.items(), key=lambda item: item[0])
        ]

        summary = self._summarize_dicts([b["metrics"] for b in grouped.values()])
        return {
            "compare_dimension": compare_dimension,
            "finance_type": finance_type,
            "company_numbers": company_numbers,
            "years": years,
            "months": months,
            "details": details,
            "summary": summary,
        }

    def get_chart_data(
        self,
        finance_type: str,
        keep_date: str,
        chart_type: str = "line",
    ) -> Dict[str, Any]:
        data = self.query_finance_data(finance_type, keep_date)
        series = [
            {
                "name": item["company_name"] or item["company_no"],
                "value": item["metrics"].get("current_amount"),
            }
            for item in data["results"]
        ]
        return {
            "chart_type": chart_type,
            "finance_type": finance_type,
            "keep_date": data["query"]["keep_date"],
            "series": series,
            "summary": data["summary"],
        }

    def list_finance_types(self) -> List[Dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            stmt = (
                select(
                    models.FinanceRecordORM.type_no,
                    models.FinanceRecordORM.type_name,
                )
                .distinct()
                .order_by(models.FinanceRecordORM.type_no.asc())
            )
            rows = session.execute(stmt).all()
        return [
            {
                "type_no": row.type_no,
                "type_name": row.type_name,
            }
            for row in rows
        ]

    def _normalize_month(self, value: str) -> date:
        value = value.strip()
        if len(value) == 7:
            value = f"{value}-01"
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
        return parsed.replace(day=1)

    def _to_dto(self, record: models.FinanceRecordORM) -> FinanceRecordDTO:
        metrics = {
            "current_amount": _decimal_to_float(record.current_amount),
            "last_year_amount": _decimal_to_float(record.last_year_amount),
            "last_year_total_amount": _decimal_to_float(record.last_year_total_amount),
            "this_year_total_amount": _decimal_to_float(record.this_year_total_amount),
            "add_amount": _decimal_to_float(record.add_amount),
            "add_rate": _decimal_to_float(record.add_rate),
            "year_add_amount": _decimal_to_float(record.year_add_amount),
            "year_add_rate": _decimal_to_float(record.year_add_rate),
        }
        return FinanceRecordDTO(
            company_no=record.company_no,
            company_name=record.company_name,
            level=record.level,
            keep_date=record.keep_date,
            type_no=record.type_no,
            type_name=record.type_name,
            metrics=metrics,
        )

    def _dto_to_dict(self, dto: FinanceRecordDTO) -> Dict[str, Any]:
        return {
            "company_no": dto.company_no,
            "company_name": dto.company_name,
            "level": dto.level,
            "keep_date": dto.keep_date.isoformat(),
            "finance_type": dto.type_no,
            "finance_type_name": dto.type_name,
            "metrics": dto.metrics,
        }

    def _summarize(self, items: Iterable[FinanceRecordDTO]) -> Dict[str, Any]:
        metrics_list = [item.metrics for item in items]
        return self._summarize_dicts(metrics_list)

    def _summarize_dicts(self, metrics_list: Iterable[Dict[str, Optional[float]]]) -> Dict[str, Any]:
        summary = self._empty_metrics()
        for metrics in metrics_list:
            self._merge_metrics(summary, metrics)
        return summary

    def _empty_metrics(self) -> Dict[str, Optional[float]]:
        return {
            "current_amount": 0.0,
            "last_year_amount": 0.0,
            "last_year_total_amount": 0.0,
            "this_year_total_amount": 0.0,
            "add_amount": 0.0,
            "add_rate": 0.0,
            "year_add_amount": 0.0,
            "year_add_rate": 0.0,
        }

    def _merge_metrics(
        self,
        base: Dict[str, Optional[float]],
        increment: Dict[str, Optional[float]],
    ) -> None:
        for key, value in increment.items():
            if value is None:
                continue
            base[key] = (base.get(key) or 0.0) + value

    def _group_key(self, dimension: str, dto: FinanceRecordDTO) -> tuple[str, str]:
        if dimension == "company":
            label = dto.company_name or dto.company_no
            return dto.company_no, label
        if dimension == "year":
            year = dto.keep_date.strftime("%Y")
            return year, year
        # default month
        month = dto.keep_date.strftime("%Y-%m")
        return month, month


__all__ = ["FinanceDataService"]
