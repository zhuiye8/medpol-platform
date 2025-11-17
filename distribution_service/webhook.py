"""Webhook 通知占位实现。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


class WebhookDispatcher:
    """将通知写入 sample_data/webhook 目录，模拟推送。"""

    def __init__(self, base_dir: str = "sample_data/webhook") -> None:
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def dispatch(self, targets: List[str], payload: Dict) -> None:
        self._counter += 1
        filename = self.base_path / f"webhook_{self._counter:04d}.json"
        data = {"targets": targets, "payload": payload}
        filename.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
