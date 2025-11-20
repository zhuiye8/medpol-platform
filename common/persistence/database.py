"""SQLAlchemy Engine / Session 工具函数。"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

from common.utils.env import load_env
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# 先加载 .env，再读取 DATABASE_URL
load_env()


def get_engine(database_url: Optional[str] = None):
    """根据配置创建 Engine。"""

    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("缺少 DATABASE_URL 配置")
    return create_engine(url, echo=False, future=True)


def get_session_factory(engine=None):
    """生成 sessionmaker，默认基于全局 Engine。"""

    engine = engine or get_engine()
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory=None) -> Generator[Session, None, None]:
    """提供事务范围内的 Session，自动提交/回滚。"""

    factory = session_factory or get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
