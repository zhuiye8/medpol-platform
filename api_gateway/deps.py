"""FastAPI dependency for DB sessions and authentication."""

from __future__ import annotations

import os
from typing import Callable, Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from common.persistence.database import get_session_factory
from common.utils.env import load_env
from common.auth import AuthService, AuthError
from common.auth.service import UserInfo

# 确保 .env 加载，启动时不缺 DATABASE_URL
load_env()


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
    """FastAPI 路由使用的 Session 生成器。"""

    session_factory = get_session_factory_cached()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ======================== Authentication Dependencies ========================

# HTTP Bearer token scheme
oauth2_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session),
):
    """
    获取当前登录用户。

    从 Authorization header 提取 Bearer token 并验证。

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        auth_service = AuthService(db)
        user_info = auth_service.get_current_user(credentials.credentials)
        return user_info
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session),
):
    """
    获取当前登录用户（可选）。

    如果未提供 token 或 token 无效，返回 None。
    """
    if credentials is None:
        return None

    try:
        auth_service = AuthService(db)
        return auth_service.get_current_user(credentials.credentials)
    except AuthError:
        return None


def require_roles(*roles: str) -> Callable:
    """
    创建角色检查依赖。

    Usage:
        @router.get("/admin")
        async def admin_endpoint(user = Depends(require_roles("admin"))):
            ...

        @router.get("/employee")
        async def employee_endpoint(user = Depends(require_roles(Roles.ADMIN))):
            ...
    """
    def role_checker(
        current_user: UserInfo = Depends(get_current_user),
    ) -> UserInfo:
        if not current_user.has_any_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(roles)}",
            )
        return current_user

    return role_checker
