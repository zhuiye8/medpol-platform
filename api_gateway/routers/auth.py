# -*- coding: utf-8 -*-
"""Authentication API routes."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api_gateway.deps import get_db_session, get_current_user, require_roles
from common.auth import AuthService, AuthError
from common.auth.service import Roles, UserInfo


router = APIRouter()


# ======================== Request/Response Schemas ========================


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response."""
    token: str
    user: "UserResponse"


class UserResponse(BaseModel):
    """User information response."""
    id: str
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    company_no: Optional[str] = None
    roles: List[str] = []
    is_active: bool = True


class RoleResponse(BaseModel):
    """Role information response."""
    id: str
    name: str
    description: Optional[str] = None


class CreateUserRequest(BaseModel):
    """Create user request body."""
    username: str
    password: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    company_no: Optional[str] = None
    roles: List[str] = []


class ChangePasswordRequest(BaseModel):
    """Change password request body."""
    old_password: str
    new_password: str


class Envelope(BaseModel):
    """Standard API response envelope."""
    code: int = 0
    message: str = "ok"
    data: Optional[dict] = None


# ======================== API Endpoints ========================


@router.post("/login", response_model=Envelope)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db_session),
) -> Envelope:
    """
    用户登录，返回 JWT token。

    - **username**: 用户名
    - **password**: 密码
    """
    try:
        auth_service = AuthService(db)
        token, user_info = auth_service.login(request.username, request.password)
        db.commit()

        return Envelope(
            code=0,
            message="ok",
            data={
                "token": token,
                "user": UserResponse(
                    id=user_info.id,
                    username=user_info.username,
                    display_name=user_info.display_name,
                    email=user_info.email,
                    company_no=user_info.company_no,
                    roles=user_info.roles,
                    is_active=user_info.is_active,
                ).model_dump(),
            },
        )
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=Envelope)
async def get_me(
    current_user: UserInfo = Depends(get_current_user),
) -> Envelope:
    """
    获取当前登录用户信息。

    需要在 Header 中携带 `Authorization: Bearer <token>`
    """
    return Envelope(
        code=0,
        message="ok",
        data={
            "user": UserResponse(
                id=current_user.id,
                username=current_user.username,
                display_name=current_user.display_name,
                email=current_user.email,
                company_no=current_user.company_no,
                roles=current_user.roles,
                is_active=current_user.is_active,
            ).model_dump(),
        },
    )


@router.get("/roles", response_model=Envelope)
async def list_roles(
    db: Session = Depends(get_db_session),
    _: UserInfo = Depends(require_roles(Roles.ADMIN)),
) -> Envelope:
    """
    获取所有角色列表。

    仅限管理员访问。
    """
    auth_service = AuthService(db)
    roles = auth_service.get_all_roles()

    return Envelope(
        code=0,
        message="ok",
        data={
            "roles": [
                RoleResponse(
                    id=role.id,
                    name=role.name,
                    description=role.description,
                ).model_dump()
                for role in roles
            ],
        },
    )


@router.post("/users", response_model=Envelope)
async def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db_session),
    _: UserInfo = Depends(require_roles(Roles.ADMIN)),
) -> Envelope:
    """
    创建新用户。

    仅限管理员访问。
    """
    try:
        auth_service = AuthService(db)
        user = auth_service.create_user(
            username=request.username,
            password=request.password,
            display_name=request.display_name,
            email=request.email,
            company_no=request.company_no,
            role_names=request.roles if request.roles else [Roles.VIEWER],
        )
        db.commit()

        return Envelope(
            code=0,
            message="ok",
            data={
                "user": UserResponse(
                    id=user.id,
                    username=user.username,
                    display_name=user.display_name,
                    email=user.email,
                    company_no=user.company_no,
                    roles=user.role_names,
                    is_active=user.is_active,
                ).model_dump(),
            },
        )
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/change-password", response_model=Envelope)
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db_session),
    current_user: UserInfo = Depends(get_current_user),
) -> Envelope:
    """
    修改当前用户密码。
    """
    auth_service = AuthService(db)

    # Verify old password
    user = auth_service.get_user_by_id(current_user.id)
    if not user or not auth_service.verify_password(request.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误",
        )

    # Update password
    user.password_hash = auth_service.hash_password(request.new_password)
    db.commit()

    return Envelope(code=0, message="密码修改成功")


# ======================== User Management (Admin Only) ========================


class UpdateUserRequest(BaseModel):
    """Update user request body."""
    display_name: Optional[str] = None
    email: Optional[str] = None
    company_no: Optional[str] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


@router.get("/users", response_model=Envelope)
async def list_users(
    db: Session = Depends(get_db_session),
    _: UserInfo = Depends(require_roles(Roles.ADMIN)),
) -> Envelope:
    """
    获取所有用户列表。

    仅限管理员访问。
    """
    auth_service = AuthService(db)
    users = auth_service.get_all_users()

    return Envelope(
        code=0,
        message="ok",
        data={
            "users": [
                UserResponse(
                    id=user.id,
                    username=user.username,
                    display_name=user.display_name,
                    email=user.email,
                    company_no=user.company_no,
                    roles=user.role_names,
                    is_active=user.is_active,
                ).model_dump()
                for user in users
            ],
        },
    )


@router.put("/users/{user_id}", response_model=Envelope)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    db: Session = Depends(get_db_session),
    _: UserInfo = Depends(require_roles(Roles.ADMIN)),
) -> Envelope:
    """
    更新用户信息。

    仅限管理员访问。
    """
    auth_service = AuthService(db)
    user = auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # Update fields if provided
    if request.display_name is not None:
        user.display_name = request.display_name
    if request.email is not None:
        user.email = request.email
    if request.company_no is not None:
        user.company_no = request.company_no
    if request.is_active is not None:
        user.is_active = request.is_active
    if request.roles is not None:
        auth_service.set_user_roles(user, request.roles)

    db.commit()

    return Envelope(
        code=0,
        message="ok",
        data={
            "user": UserResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                email=user.email,
                company_no=user.company_no,
                roles=user.role_names,
                is_active=user.is_active,
            ).model_dump(),
        },
    )


@router.delete("/users/{user_id}", response_model=Envelope)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db_session),
    current_user: UserInfo = Depends(require_roles(Roles.ADMIN)),
) -> Envelope:
    """
    禁用用户（软删除）。

    仅限管理员访问。不能删除自己。
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    auth_service = AuthService(db)
    user = auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # Soft delete - just disable the user
    user.is_active = False
    db.commit()

    return Envelope(code=0, message="用户已禁用")
