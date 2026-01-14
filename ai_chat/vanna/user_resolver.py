"""User resolver for Vanna Agent with auth support."""

from __future__ import annotations

from typing import Optional

from vanna.core.user import RequestContext, User
from vanna.core.user.resolver import UserResolver

from common.auth.service import Roles


class SimpleUserResolver(UserResolver):
    """Resolve to a fixed demo user (no auth)."""

    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(id="demo-user", username="demo", metadata=request_context.metadata or {})


class AuthUserResolver(UserResolver):
    """Resolve user from authenticated context.

    从 request_context.metadata 中提取已验证的用户信息。

    预期的 metadata 结构：
    {
        "user_id": "user-xxx",
        "username": "admin",
        "user_role": "admin",
        "display_name": "系统管理员",
        ...
    }
    """

    def __init__(self, default_role: str = Roles.VIEWER):
        """
        Args:
            default_role: 未认证用户的默认角色
        """
        self.default_role = default_role

    async def resolve_user(self, request_context: RequestContext) -> User:
        metadata = request_context.metadata or {}

        # 从 metadata 提取用户信息
        user_id = metadata.get("user_id", "anonymous")
        username = metadata.get("username", "anonymous")
        user_role = metadata.get("user_role", self.default_role)

        # 构建用户对象
        return User(
            id=user_id,
            username=username,
            metadata={
                **metadata,
                "role": user_role,  # 确保 role 字段存在
            }
        )

    @staticmethod
    def get_user_role(user: User) -> str:
        """从 User 对象获取角色。"""
        return user.metadata.get("role", Roles.VIEWER)


__all__ = ["SimpleUserResolver", "AuthUserResolver"]
