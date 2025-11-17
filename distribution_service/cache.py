"""缓存/搜索写入逻辑（占位实现）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class LocalCacheWriter:
    """简单地将数据写入 sample_data/cache 目录以模拟缓存。"""

    def __init__(self, base_dir: str = "sample_data/cache") -> None:
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upsert_article(self, article: Dict) -> None:
        article_id = article["id"]
        path = self.base_path / f"{article_id}.json"
        path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
