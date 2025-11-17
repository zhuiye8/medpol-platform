"""FastAPI 依赖：数据库 Session 等。"""

from __future__ import annotations

import os
from typing import Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from common.persistence.database import get_session_factory


SessionLocal = None


def get_session_factory_cached():
    global SessionLocal  # pylint: disable=global-statement
    if SessionLocal is None:
        if not os.getenv("DATABASE_URL"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="未配置数据库，无法提供 API 服务",
            )
        SessionLocal = get_session_factory()
    return SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI 依赖，提供 SQLAlchemy Session。"""

    session_factory = get_session_factory_cached()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
