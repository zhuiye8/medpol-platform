"""财务数据拉取工具"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from common.utils.config import get_settings

logger = logging.getLogger(__name__)


class FinanceDataFetcherError(RuntimeError):
    """财务数据获取失败"""


class FinanceDataFetcher:
    """封装 financeDate/dataList 接口的拉取逻辑"""

    def __init__(self) -> None:
        settings = get_settings()
        self.endpoint = settings.finance_data_endpoint
        self.timeout = settings.finance_api_timeout

    def fetch(self, keep_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """拉取财务数据"""

        params: Dict[str, Any] = {}
        if keep_date:
            params["keepDate"] = keep_date
            logger.info("按月拉取财务数据: %s", keep_date)
        else:
            logger.info("拉取全量财务数据")

        try:
            response = httpx.post(self.endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - 网络异常
            logger.error("财务数据接口请求失败: %s", exc)
            raise FinanceDataFetcherError(f"HTTP 请求失败: {exc}") from exc

        data = response.json()
        payload: Any
        code = None
        if isinstance(data, dict):
            code = data.get("code")
            payload = data.get("data", [])
        else:
            payload = data

        if code not in (None, "0000", "200", "0"):
            raise FinanceDataFetcherError(f"接口返回异常 code={code} msg={data}")

        if not isinstance(payload, list):
            raise FinanceDataFetcherError("接口返回异常，data 字段不是列表")

        logger.info("拉取完成，记录数: %d", len(payload))
        return payload
