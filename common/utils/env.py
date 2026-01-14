"""统一加载 .env 的小工具，方便 uvicorn/Celery/脚本自动读取环境变量。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable

# 在导入任何可能使用 httpx 的模块前，设置 NO_PROXY 让本地请求绑过代理
# 这解决了 Ollama 等本地服务因代理导致的 502 错误
if "NO_PROXY" not in os.environ:
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"
else:
    # 确保 localhost 在 NO_PROXY 列表中
    existing = os.environ["NO_PROXY"]
    if "localhost" not in existing:
        os.environ["NO_PROXY"] = f"{existing},localhost,127.0.0.1"

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_env(paths: Iterable[str | Path] | None = None) -> bool:
    """
    依次尝试加载 .env，默认会找当前工作目录和仓库根目录。
    返回是否至少成功加载一次，已经加载过会缓存避免重复。
    """

    candidates = list(paths) if paths is not None else [Path.cwd() / ".env", REPO_ROOT / ".env"]
    loaded = False
    for path in candidates:
        p = Path(path)
        if not p.exists():
            continue
        load_dotenv(p, override=False)
        loaded = True
    return loaded


# 模块导入即尝试加载一次，确保 os.getenv 可读到 .env
load_env()
