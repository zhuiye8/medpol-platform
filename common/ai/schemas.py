"""AI 结构化输出 Schema 定义与 JSON Schema 转换工具。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AnalysisResultSchema(BaseModel):
    """联环视角分析结果。"""

    content: str = Field(..., description="联环视角的结论与行动建议")
    is_positive_policy: Optional[bool] = Field(
        default=None, description="政策/招采/制度类的利好或风险判断；其他类型用 null"
    )


class TranslationCheckSchema(BaseModel):
    """翻译判定结果。"""

    is_chinese: bool = Field(..., description="是否主要为中文/CJK 内容")
    detected_language: str = Field(..., description="检测到的语言代码，如 zh、en、ja")
    confidence: float = Field(..., ge=0, le=1, description="语言检测置信度 0-1")


class CapabilityDecisionSchema(BaseModel):
    """对话工具选择决策。"""

    use_finance: bool = Field(..., description="是否需要金融/财务类工具")
    use_knowledge: bool = Field(..., description="是否需要知识库/政策检索工具")
    allow_free_answer: bool = Field(..., description="无工具时是否允许直接回答")
    category: Optional[str] = Field(default=None, description="可选的垂直类别标签")


class SummarySchema(BaseModel):
    """短摘要输出。"""

    summary: str = Field(..., description="简短摘要")
    key_points: List[str] = Field(default_factory=list, description="要点列表")


def _strip_titles(obj: object) -> None:
    """移除 JSON Schema 中的 title/description，避免严格模式报错。"""

    if isinstance(obj, dict):
        obj.pop("title", None)
        obj.pop("description", None)
        for value in obj.values():
            _strip_titles(value)
    elif isinstance(obj, list):
        for item in obj:
            _strip_titles(item)


def pydantic_to_json_schema(model_cls: type[BaseModel]) -> dict:
    """
    将 Pydantic 模型转换为满足 OpenAI/DeepSeek 严格模式的 JSON Schema。

    - 移除 title/description，避免部分 provider 校验失败
    - 默认追加 additionalProperties: false
    """

    schema = model_cls.model_json_schema()
    _strip_titles(schema)
    if "additionalProperties" not in schema:
        schema["additionalProperties"] = False
    return schema


__all__ = [
    "AnalysisResultSchema",
    "TranslationCheckSchema",
    "CapabilityDecisionSchema",
    "SummarySchema",
    "pydantic_to_json_schema",
]
