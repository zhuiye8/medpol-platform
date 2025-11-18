"""API Gateway 入口，FastAPI 实例。"""

from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import admin, articles, scheduler, ai_chat


def _load_allowed_origins() -> tuple[list[str], bool]:
    """解析允许的前端地址，若未配置则默认放开跨域。"""

    raw = os.getenv("ADMIN_PORTAL_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if not origins:
        # 默认开放公开 API，返回 "*" 并关闭凭据支持
        return ["*"], False
    return origins, True


app = FastAPI(title="Med Policy Platform API", version="0.1.0")
allow_origins, allow_credentials = _load_allowed_origins()

# 配置文件日志（用于调试），如未设置 LOG_FILE_PATH 则仅输出到 stdout
log_file = os.getenv("LOG_FILE_PATH")
if log_file:
    handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)

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
    """基础健康检查。"""

    return {"code": 0, "msg": "success", "data": {"status": "ok"}}
