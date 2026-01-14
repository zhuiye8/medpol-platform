# -*- coding: utf-8 -*-
"""Authentication service with JWT support."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from common.persistence.models import UserORM, RoleORM
from common.utils.config import get_settings


class AuthError(Exception):
    """Authentication error."""
    pass


class TokenData(BaseModel):
    """JWT token payload."""
    user_id: str
    username: str
    roles: List[str]
    exp: datetime


class UserInfo(BaseModel):
    """User information returned from auth service."""
    id: str
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    company_no: Optional[str] = None
    roles: List[str] = []
    is_active: bool = True

    @property
    def primary_role(self) -> Optional[str]:
        """Get primary (first) role."""
        return self.roles[0] if self.roles else None

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)


class AuthService:
    """Authentication and authorization service."""

    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            password_bytes = plain_password.encode("utf-8")
            hashed_bytes = hashed_password.encode("utf-8")
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception:
            return False

    def create_access_token(self, user: UserORM, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token for a user."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.settings.jwt_expire_minutes)

        expire = datetime.now(timezone.utc) + expires_delta
        to_encode = {
            "sub": user.id,
            "username": user.username,
            "roles": user.role_names,
            "exp": expire,
        }
        return jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    def verify_token(self, token: str) -> TokenData:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            username = payload.get("username")
            roles = payload.get("roles", [])
            exp = payload.get("exp")

            if not user_id or not username:
                raise AuthError("无效的 token 载荷")

            return TokenData(
                user_id=user_id,
                username=username,
                roles=roles,
                exp=datetime.fromtimestamp(exp, tz=timezone.utc),
            )
        except JWTError as e:
            raise AuthError(f"Token 验证失败: {str(e)}")

    def get_user_by_username(self, username: str) -> Optional[UserORM]:
        """Get user by username with roles loaded."""
        return (
            self.session.query(UserORM)
            .options(joinedload(UserORM.roles))
            .filter(UserORM.username == username)
            .first()
        )

    def get_user_by_id(self, user_id: str) -> Optional[UserORM]:
        """Get user by ID with roles loaded."""
        return (
            self.session.query(UserORM)
            .options(joinedload(UserORM.roles))
            .filter(UserORM.id == user_id)
            .first()
        )

    def login(self, username: str, password: str) -> tuple[str, UserInfo]:
        """
        Authenticate user and return JWT token.

        Returns:
            Tuple of (token, user_info)

        Raises:
            AuthError: If authentication fails
        """
        user = self.get_user_by_username(username)
        if not user:
            raise AuthError("用户名或密码错误")

        if not self.verify_password(password, user.password_hash):
            raise AuthError("用户名或密码错误")

        if not user.is_active:
            raise AuthError("账号已被禁用")

        token = self.create_access_token(user)
        user_info = UserInfo(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            company_no=user.company_no,
            roles=user.role_names,
            is_active=user.is_active,
        )
        return token, user_info

    def get_current_user(self, token: str) -> UserInfo:
        """
        Get current user from token.

        Raises:
            AuthError: If token is invalid or user not found
        """
        token_data = self.verify_token(token)
        user = self.get_user_by_id(token_data.user_id)
        if not user:
            raise AuthError("用户不存在")
        if not user.is_active:
            raise AuthError("账号已被禁用")

        return UserInfo(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            company_no=user.company_no,
            roles=user.role_names,
            is_active=user.is_active,
        )

    def create_user(
        self,
        username: str,
        password: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        company_no: Optional[str] = None,
        role_names: Optional[List[str]] = None,
    ) -> UserORM:
        """
        Create a new user.

        Args:
            username: Unique username
            password: Plain text password (will be hashed)
            display_name: Display name
            email: Email address
            company_no: Company code
            role_names: List of role names to assign

        Returns:
            Created user

        Raises:
            AuthError: If username already exists
        """
        existing = self.get_user_by_username(username)
        if existing:
            raise AuthError(f"用户名 {username} 已存在")

        user = UserORM(
            id=f"user-{uuid.uuid4().hex[:12]}",
            username=username,
            password_hash=self.hash_password(password),
            display_name=display_name,
            email=email,
            company_no=company_no,
            is_active=True,
        )

        if role_names:
            roles = (
                self.session.query(RoleORM)
                .filter(RoleORM.name.in_(role_names))
                .all()
            )
            user.roles = roles

        self.session.add(user)
        self.session.flush()
        return user

    def get_all_roles(self) -> List[RoleORM]:
        """Get all available roles."""
        return self.session.query(RoleORM).all()

    def get_all_users(self) -> List[UserORM]:
        """Get all users."""
        return self.session.query(UserORM).all()

    def set_user_roles(self, user: UserORM, role_names: List[str]) -> None:
        """Set user roles (replace all existing roles)."""
        roles = (
            self.session.query(RoleORM)
            .filter(RoleORM.name.in_(role_names))
            .all()
        )
        user.roles = roles
        self.session.flush()

    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user."""
        user = self.get_user_by_id(user_id)
        if not user:
            raise AuthError("用户不存在")

        role = self.session.query(RoleORM).filter(RoleORM.name == role_name).first()
        if not role:
            raise AuthError(f"角色 {role_name} 不存在")

        if role not in user.roles:
            user.roles.append(role)
            self.session.flush()
            return True
        return False

    def remove_role(self, user_id: str, role_name: str) -> bool:
        """Remove a role from a user."""
        user = self.get_user_by_id(user_id)
        if not user:
            raise AuthError("用户不存在")

        role = self.session.query(RoleORM).filter(RoleORM.name == role_name).first()
        if not role:
            raise AuthError(f"角色 {role_name} 不存在")

        if role in user.roles:
            user.roles.remove(role)
            self.session.flush()
            return True
        return False


# Role constants for easy reference
class Roles:
    """用户角色定义。

    只保留三个核心角色：
    - admin: 管理员，全部权限
    - finance: 财务人员，只有财务查询
    - viewer: 普通用户，政策检索+员工基础字段
    """
    ADMIN = "admin"
    FINANCE = "finance"
    VIEWER = "viewer"

    # Role groups for permission checks
    EMPLOYEE_FULL = {ADMIN}  # 可以访问员工全字段
    EMPLOYEE_BASIC = {ADMIN, VIEWER}  # 可以访问员工基础字段
    FINANCE_ACCESS = {ADMIN, FINANCE}  # 可以访问财务数据
    ALL_ROLES = {ADMIN, FINANCE, VIEWER}
