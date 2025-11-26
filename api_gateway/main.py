"""API Gateway FastAPI entrypoint."""

from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from common.utils.env import load_env

# 确保 .env 已加载，便于 uvicorn 直接运行
load_env()

from .routers import admin, articles, scheduler, ai_chat


def _load_allowed_origins() -> tuple[list[str], bool]:
    """读取前端允许的域名，未配置则默认放开。"""

    raw = os.getenv("ADMIN_PORTAL_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if not origins:
        # 默认开放，API 和 Admin Portal 联调更方便
        return ["*"], False
    return origins, True


app = FastAPI(title="Med Policy Platform API", version="0.1.0")
allow_origins, allow_credentials = _load_allowed_origins()

# 记录到文件日志（可选）；未设置 LOG_FILE_PATH 则输出到标准输出
log_file = os.getenv("LOG_FILE_PATH")
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
root_logger = logging.getLogger()
# 若未设置处理器，则默认输出到标准输出
if not root_logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(stream_handler)
if log_file:
    handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
root_logger.setLevel(log_level)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(articles.router, prefix="/v1/articles", tags=["articles"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
app.include_router(scheduler.router, prefix="/v1", tags=["scheduler"])
app.include_router(ai_chat.router, prefix="/v1/ai", tags=["ai-chat"])


@app.get("/healthz")
async def health_check() -> dict:
    """存活检查。"""

    return {"code": 0, "msg": "success", "data": {"status": "ok"}}
