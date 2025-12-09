"""API Gateway FastAPI entrypoint."""

from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.utils.env import load_env

# ensure .env is loaded for uvicorn direct run
load_env()

from .routers import admin, articles, scheduler
from api_gateway.routers import admin_finance, admin_embeddings
from ai_chat.core import router as ai_chat_router


def _load_allowed_origins() -> tuple[list[str], bool, str | None]:
    """Read allowed origins for Admin Portal; default to open."""

    raw = os.getenv("ADMIN_PORTAL_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if not origins:
        # default open; admin portal local dev works without extra config
        return ["*"], False, ".*"
    return origins, True, None


app = FastAPI(title="Med Policy Platform API", version="0.1.0")
allow_origins, allow_credentials, allow_origin_regex = _load_allowed_origins()

# logging setup: stdout by default, optional file rotating
log_file = os.getenv("LOG_FILE_PATH")
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
root_logger = logging.getLogger()
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
    allow_origin_regex=allow_origin_regex,
)

app.include_router(articles.router, prefix="/v1/articles", tags=["articles"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
app.include_router(scheduler.router, prefix="/v1", tags=["scheduler"])
app.include_router(ai_chat_router, prefix="/v1/ai", tags=["ai-chat-new"])
app.include_router(admin_finance.router, prefix="/v1/admin", tags=["admin-finance"])
app.include_router(admin_embeddings.router, prefix="/v1/admin", tags=["admin-embeddings"])


@app.get("/healthz")
async def health_check() -> dict:
    """Liveness probe."""

    return {"code": 0, "msg": "success", "data": {"status": "ok"}}
