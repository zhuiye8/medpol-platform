import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from formatter_service.worker import process_raw_article  # noqa: E402

OUTBOX = ROOT / "sample_data" / "outbox"
NORMALIZED = ROOT / "sample_data" / "normalized"
NORMALIZED.mkdir(parents=True, exist_ok=True)

processed = 0
skipped = 0

for raw_file in sorted(OUTBOX.glob("raw_*.json")):
    payload = json.loads(raw_file.read_text(encoding="utf-8"))
    result = process_raw_article(payload)
    if result.get("skipped"):
        skipped += 1
        print(f"跳过 {raw_file.name}: {result.get('reason')}")
        continue
    processed += 1
    article = result["article"]
    target = NORMALIZED / f"article_{result['article_id']}.json"
    target.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已归档 {raw_file.name} -> {target.name}")

print(f"完成，成功 {processed} 条，跳过 {skipped} 条。")
