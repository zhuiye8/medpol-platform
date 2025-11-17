"""财务API HTTP客户端

封装与外部财务报表API的HTTP通信逻辑。
"""

import json
import logging
from typing import List, Dict, Optional, Any

import httpx

from .models import FinanceQueryParams, FinanceCompareParams

logger = logging.getLogger(__name__)


class FinanceAPIError(Exception):
    """财务API错误基类"""
    pass


class FinanceDataNotFoundError(FinanceAPIError):
    """数据不存在错误"""
    pass


class FinanceValidationError(FinanceAPIError):
    """参数验证错误"""
    pass


class FinanceAPIClient:
    """财务API HTTP客户端

    负责与外部财务报表API进行HTTP通信。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """初始化客户端

        Args:
            base_url: API基础URL（可选，默认从配置读取）
            timeout: 请求超时时间（秒，可选，默认从配置读取）
        """
        from common.utils.config import get_settings

        settings = get_settings()
        self.base_url = (base_url or settings.finance_api_base_url).rstrip("/")
        self.timeout = timeout or settings.finance_api_timeout
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """获取HTTP客户端实例（懒加载）"""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _parse_response(self, response: httpx.Response) -> Any:
        """解析API响应

        处理返回string类型的情况（可能是JSON字符串）

        Args:
            response: HTTP响应对象

        Returns:
            解析后的数据

        Raises:
            FinanceAPIError: API调用失败
        """
        if response.status_code != 200:
            raise FinanceAPIError(
                f"API请求失败: HTTP {response.status_code}, {response.text}"
            )

        data = response.json()

        # 如果返回的是字符串类型，尝试解析为JSON
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("返回数据不是有效的JSON字符串: %s", data[:100])

        return data

    def get_finance_date(
        self,
        finance_type: str,
        keep_date: str,
        company_numbers: Optional[List[str]] = None
    ) -> List[Dict]:
        """查询财务数据

        Args:
            finance_type: 财务类型编号（"01"-"08"）
            keep_date: 记账日期（格式：YYYY-MM）
            company_numbers: 可选的公司编号列表

        Returns:
            财务数据列表

        Raises:
            FinanceAPIError: API调用失败
        """
        logger.info(
            "查询财务数据: finance_type=%s, keep_date=%s, companies=%s",
            finance_type,
            keep_date,
            company_numbers,
        )

        # 构建参数
        if company_numbers:
            # httpx支持多值参数: [(key, value1), (key, value2)]
            params = [
                ("financeType", finance_type),
                ("keepDate", keep_date),
            ]
            for cn in company_numbers:
                params.append(("companyNo", cn))
        else:
            params = {
                "financeType": finance_type,
                "keepDate": keep_date,
            }

        try:
            response = self.client.post(
                f"{self.base_url}/finance/getFinanceDate",
                params=params
            )
            data = self._parse_response(response)

            logger.info("查询成功，返回%d条数据", len(data) if isinstance(data, list) else 0)
            return data if isinstance(data, list) else []

        except httpx.HTTPError as e:
            logger.error("HTTP请求失败: %s", e, exc_info=True)
            raise FinanceAPIError(f"HTTP请求失败: {e}") from e

    def get_finance_date_compare(
        self,
        compare_type: str,
        company_numbers: List[str],
        years: List[str],
        months: List[str]
    ) -> Dict:
        """对比分析财务数据

        Args:
            compare_type: 对比类型（"year"/"month"/"company"）
            company_numbers: 公司编号列表
            years: 年份列表
            months: 月份列表

        Returns:
            对比分析数据

        Raises:
            FinanceAPIError: API调用失败
        """
        logger.info(
            "对比财务数据: type=%s, companies=%s, years=%s, months=%s",
            compare_type,
            company_numbers,
            years,
            months,
        )

        # 构建多值参数
        params = [("compareType", compare_type)]

        for cn in company_numbers:
            params.append(("companyNos", cn))
        for year in years:
            params.append(("year", year))
        for month in months:
            params.append(("month", month))

        try:
            response = self.client.post(
                f"{self.base_url}/finance/getFinanceDateCompare",
                params=params
            )
            data = self._parse_response(response)

            logger.info("对比查询成功")
            return data if isinstance(data, dict) else {}

        except httpx.HTTPError as e:
            logger.error("HTTP请求失败: %s", e, exc_info=True)
            raise FinanceAPIError(f"HTTP请求失败: {e}") from e

    def get_finance_date_graph(
        self,
        finance_type: str,
        keep_date: str
    ) -> Dict:
        """获取图表数据

        Args:
            finance_type: 财务类型编号
            keep_date: 记账日期

        Returns:
            图表数据

        Raises:
            FinanceAPIError: API调用失败
        """
        logger.info("获取图表数据: finance_type=%s, keep_date=%s", finance_type, keep_date)

        params = {
            "financeType": finance_type,
            "keepDate": keep_date,
        }

        try:
            response = self.client.post(
                f"{self.base_url}/finance/getFinanceDateGraph",
                params=params
            )
            data = self._parse_response(response)

            logger.info("图表数据获取成功")
            return data if isinstance(data, dict) else {}

        except httpx.HTTPError as e:
            logger.error("HTTP请求失败: %s", e, exc_info=True)
            raise FinanceAPIError(f"HTTP请求失败: {e}") from e

    def get_finance_type(self) -> List[Dict]:
        """获取财务类型列表

        Returns:
            财务类型列表

        Raises:
            FinanceAPIError: API调用失败
        """
        logger.info("获取财务类型列表")

        try:
            response = self.client.post(f"{self.base_url}/finance/getFinanceType")
            result = self._parse_response(response)

            # IResponse格式: {"code": "200", "data": [...], "msg": "..."}
            if isinstance(result, dict) and "data" in result:
                logger.info("获取到%d个财务类型", len(result["data"]))
                return result["data"]

            logger.info("获取到%d个财务类型", len(result) if isinstance(result, list) else 0)
            return result if isinstance(result, list) else []

        except httpx.HTTPError as e:
            logger.error("HTTP请求失败: %s", e, exc_info=True)
            raise FinanceAPIError(f"HTTP请求失败: {e}") from e

    def insert_finance_date(self, finance_type_list: List[Dict]) -> List[Dict]:
        """新增报表数据

        Args:
            finance_type_list: 报表数据列表

        Returns:
            插入后的数据列表

        Raises:
            FinanceAPIError: API调用失败
        """
        logger.info("新增财务数据: %d条", len(finance_type_list))

        try:
            response = self.client.post(
                f"{self.base_url}/finance/insertFinanceDate",
                json=finance_type_list
            )
            data = self._parse_response(response)

            logger.info("数据插入成功")
            return data if isinstance(data, list) else []

        except httpx.HTTPError as e:
            logger.error("HTTP请求失败: %s", e, exc_info=True)
            raise FinanceAPIError(f"HTTP请求失败: {e}") from e

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        if self._client is not None:
            self._client.close()
            self._client = None

    def close(self):
        """关闭HTTP客户端"""
        if self._client is not None:
            self._client.close()
            self._client = None
