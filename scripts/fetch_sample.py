"""抓取药渡云前沿动态最新一条，输出示例数据。"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler_service.scheduler import run_crawler


def fetch_latest_pharnex() -> None:
    articles = run_crawler(
        "pharnex_frontier",
        {"meta": {"max_pages": 1, "page_size": 1}},
    )
    if not articles:
        print("未获取到药渡云数据")
        return
    sample_dir = Path("sample_data/examples")
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_path = sample_dir / "pharnex_frontier_latest.json"
    with sample_path.open("w", encoding="utf-8") as fh:
        json.dump(articles[0].model_dump(mode="json"), fh, ensure_ascii=False, indent=2)
    print(f"示例数据已写入 {sample_path}")


if __name__ == "__main__":
    fetch_latest_pharnex()
