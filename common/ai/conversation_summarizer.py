"""会话摘要生成，使用小模型优先，降低成本。"""

from __future__ import annotations

from typing import List

from common.ai.providers import AIProviderFactory
from common.utils.config import get_settings


class ConversationSummarizer:
    """会话摘要生成器，复用 ProviderFactory，可选指定模型。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider_factory = AIProviderFactory()

    def summarize(self, messages: List[dict]) -> str:
        """
        对若干轮对话生成简短中文摘要，仅保留核心意图与关键信息。
        messages: [{"role": "...", "content": "..."}]
        """
        if not messages:
            return ""

        # 选择摘要模型：优先 MEMORY_SUMMARY_MODEL，其次 router 用小模型
        model_override = self.settings.memory_summary_model or None
        bundle = self.provider_factory.get_client(purpose="router" if not model_override else "router")
        snippet = "\n".join(
            f"{m.get('role')}: {m.get('content') or ''}" for m in messages[-10:]
        )[:2000]
        prompt = (
            "请用简短中文总结以下对话，保留核心意图、已讨论的关键点、重要数字/时间，控制在120字以内：\n"
            f"{snippet}"
        )
        response = bundle.client.chat.completions.create(
            model=model_override or bundle.model,
            messages=[
                {"role": "system", "content": "你是会话摘要助手，只输出简洁摘要。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()


__all__ = ["ConversationSummarizer"]
