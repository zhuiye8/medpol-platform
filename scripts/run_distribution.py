"""读取 normalized 数据并触发分发逻辑。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from distribution_service.worker import process_article_file  # noqa: E402


def main():
    normalized_dir = ROOT / "sample_data" / "normalized"
    files = sorted(normalized_dir.glob("article_*.json"))
    if not files:
        print("ℹ️ 未找到 normalized 数据，请先运行 formatter/AI 流程。")
        return
    for file_path in files:
        process_article_file(file_path, targets=["webhook:demo"])
        print(f"已分发 {file_path.name}")


if __name__ == "__main__":
    main()
