"""Simple user resolver for Vanna Agent."""

from __future__ import annotations

from vanna.core.user import RequestContext, User
from vanna.core.user.resolver import UserResolver


class SimpleUserResolver(UserResolver):
    """Resolve to a fixed demo user (no auth)."""

    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(id="demo-user", username="demo", metadata=request_context.metadata or {})


__all__ = ["SimpleUserResolver"]
