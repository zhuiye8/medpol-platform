"""财务API数据模型

使用Pydantic定义请求和响应的数据模型。
"""

from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class FinanceQueryParams(BaseModel):
    """财务数据查询参数"""

    finance_type: str = Field(
        ...,
        pattern="^0[1-8]$",
        description="财务类型编号（01-08）"
    )
    keep_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="记账日期，格式：YYYY-MM"
    )
    company_numbers: Optional[List[str]] = Field(
        None,
        description="公司编号列表（可选）"
    )

    @validator('finance_type')
    def validate_finance_type(cls, v):
        """验证财务类型"""
        valid_types = ["01", "02", "03", "04", "05", "06", "07", "08"]
        if v not in valid_types:
            raise ValueError(f"无效的财务类型，必须是以下之一：{valid_types}")
        return v


class FinanceCompareParams(BaseModel):
    """财务数据对比参数"""

    compare_dimension: str = Field(
        ...,
        description="对比维度：year/month/company"
    )
    finance_type: str = Field(
        ...,
        pattern="^0[1-8]$",
        description="财务类型编号"
    )
    company_numbers: List[str] = Field(
        ...,
        min_items=1,
        description="公司编号列表"
    )
    years: List[str] = Field(
        ...,
        min_items=1,
        description="年份列表"
    )
    months: List[str] = Field(
        ...,
        min_items=1,
        description="月份列表"
    )

    @validator('compare_dimension')
    def validate_compare_dimension(cls, v):
        """验证对比维度"""
        valid_dimensions = ["year", "month", "company"]
        if v not in valid_dimensions:
            raise ValueError(f"无效的对比维度，必须是以下之一：{valid_dimensions}")
        return v


class FinanceDataItem(BaseModel):
    """财务数据项（报表数据表模型）"""

    id: Optional[int] = None
    company_id: Optional[int] = Field(None, alias="companyId")
    company_no: Optional[str] = Field(None, alias="companyNo")
    company_name: Optional[str] = Field(None, alias="companyName")
    company_address: Optional[str] = Field(None, alias="companyAddress")
    high_company_no: Optional[str] = Field(None, alias="highCompanyNo")
    level: Optional[str] = None

    type_no: Optional[str] = Field(None, alias="typeNo")
    keep_date: Optional[str] = Field(None, alias="keepDate")

    # 金额数据
    current_amt: Optional[float] = Field(None, alias="currentAmt")
    last_year_amt: Optional[float] = Field(None, alias="lastYearAmt")
    this_year_total_amt: Optional[float] = Field(None, alias="thisYearTotalAmt")
    last_year_total_amt: Optional[float] = Field(None, alias="lastYearTotalAmt")

    # 增长分析
    add_amt: Optional[float] = Field(None, alias="addAmt")
    add_rate: Optional[float] = Field(None, alias="addRate")
    year_add_amt: Optional[float] = Field(None, alias="yearAddAmt")
    year_add_rate: Optional[float] = Field(None, alias="yearAddRate")

    # 其他
    remarks: Optional[str] = None

    # 递归结构：子公司
    sub_company: Optional[List["FinanceDataItem"]] = Field(None, alias="subCompany")

    class Config:
        allow_population_by_field_name = True


class FinanceTypeItem(BaseModel):
    """财务类型项（报表类别列表模型）"""

    id: Optional[int] = None
    type_no: str = Field(..., alias="typeNo", description="类型编号")
    type_name: str = Field(..., alias="typeName", description="类型名称")
    type_status: Optional[str] = Field(None, alias="typeStatus", description="类型状态")

    class Config:
        allow_population_by_field_name = True


class FormattedFinanceData(BaseModel):
    """格式化的财务数据响应"""

    query: dict = Field(..., description="查询参数")
    results: List[dict] = Field(..., description="查询结果列表")
    summary: Optional[dict] = Field(None, description="汇总信息")


class FormattedCompareData(BaseModel):
    """格式化的对比分析数据响应"""

    compare_dimension: str = Field(..., description="对比维度")
    finance_type: str = Field(..., description="财务类型")
    summary: dict = Field(..., description="汇总信息")
    details: List[dict] = Field(..., description="详细数据")
    insights: Optional[List[str]] = Field(None, description="分析洞察")


# 允许递归模型
FinanceDataItem.model_rebuild()
