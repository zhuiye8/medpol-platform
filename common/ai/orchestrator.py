"""轻量型能力调度器"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List

from common.ai.prompts import DECIDER_SYSTEM_PROMPT, PERSONAS, PROMPT_SECTIONS
from common.utils.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class OrchestratedContext:
    persona: str
    prompt: str
    use_finance: bool
    use_knowledge: bool
    allow_free_answer: bool


@dataclass
class CapabilityDecision:
    use_finance: bool
    use_knowledge: bool


class AbilityRouter:
    """使用轻量 LLM + 规则判断所需能力"""

    def __init__(self, provider_factory) -> None:
        self.provider_factory = provider_factory
        self.settings = get_settings()
        self.enable_cache = bool(self.settings.memory_enable_stagea_cache)
        self._cache: dict[str, CapabilityDecision] = {}

    def resolve(self, persona: str, last_user_message: str) -> OrchestratedContext:
        persona_key = persona if persona in PERSONAS else "general"
        config = PERSONAS[persona_key]

        decision = self._decide(last_user_message)

        use_finance = decision.use_finance or config.get("force_finance", False)
        use_knowledge = decision.use_knowledge

        sections = [PROMPT_SECTIONS[name] for name in config["prompt_sections"]]
        prompt = "\n\n".join(sections)

        logger.info(
            "能力调度 persona=%s use_finance=%s use_knowledge=%s",
            persona_key,
            use_finance,
            use_knowledge,
        )

        return OrchestratedContext(
            persona=persona_key,
            prompt=prompt,
            use_finance=use_finance,
            use_knowledge=use_knowledge,
            allow_free_answer=config.get("allow_free_answer", True),
        )

    def _decide(self, user_message: str) -> CapabilityDecision:
        cache_key = None
        if self.enable_cache:
            cache_key = str(hash(user_message))
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            client_bundle = self.provider_factory.get_client(purpose="router")
            response = client_bundle.client.chat.completions.create(
                model=client_bundle.model,
                messages=[
                    {"role": "system", "content": DECIDER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message or ""},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            decision = CapabilityDecision(
                use_finance=bool(data.get("needs_finance")),
                use_knowledge=bool(data.get("needs_knowledge")),
            )
        except Exception as exc:  # pragma: no cover - 兜底
            logger.warning("能力判定失败，使用 fallback: %s", exc)
            decision = self._fallback_decision(user_message)

        if cache_key:
            self._cache[cache_key] = decision
        return decision

    def _fallback_decision(self, user_message: str) -> CapabilityDecision:
        finance_keywords = ["收入", "利润", "营业", "税", "净利", "营收", "财报", "财务"]
        knowledge_keywords = ["政策", "法规", "文章", "通知", "申报", "指南"]
        use_finance = any(keyword in user_message for keyword in finance_keywords)
        use_knowledge = any(keyword in user_message for keyword in knowledge_keywords)
        return CapabilityDecision(use_finance=use_finance, use_knowledge=use_knowledge)


__all__ = ["AbilityRouter", "OrchestratedContext"]
