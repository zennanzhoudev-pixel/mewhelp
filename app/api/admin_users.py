"""管理员账号与角色管理。"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.core import security
from app.core.deps import require_admin
from app.db import repository

router = APIRouter(
    prefix="/api/admin/users",
    dependencies=[Depends(require_admin)],
)

ROLES = {"admin", "agent", "viewer", "customer"}
STATUSES = {"active", "disabled"}
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    role: str = "customer"
    display_name: str | None = Field(default=None, max_length=64)
    phone: str | None = None


class UpdateUserRequest(BaseModel):
    role: str | None = None
    status: str | None = None
    display_name: str | None = Field(default=None, max_length=64)
    phone: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


def _phone(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"[\s-]", "", value)
    if not PHONE_RE.fullmatch(value):
        raise HTTPException(status_code=422, detail="手机号格式不正确")
    return value


def _out(u) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "phone": u.phone,
        "role": u.role,
        "status": u.status,
        "tenant_id": u.tenant_id,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _tenant(request) -> str:
    return getattr(request.state, "tenant_id", None) or "default"


@router.get("")
async def list_users(request: Request, query: str = Query("", max_length=64)) -> dict:
    rows = await repository.list_users(_tenant(request), query)
    return {"items": [_out(u) for u in rows]}


@router.post("")
async def create_user(req: CreateUserRequest, request: Request) -> dict:
    if req.role not in ROLES:
        raise HTTPException(status_code=422, detail="角色不合法")
    if await repository.get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    phone = _phone(req.phone)
    if phone and await repository.get_user_by_phone(phone):
        raise HTTPException(status_code=409, detail="手机号已存在")
    try:
        uid = await repository.create_managed_user(
            req.username, security.hash_password(req.password), req.role, _tenant(request),
            phone=phone, display_name=req.display_name or req.username,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="用户名或手机号已存在") from exc
    return _out(await repository.get_user_by_id(uid))


@router.patch("/{user_id}")
async def update_user(user_id: int, req: UpdateUserRequest, request: Request) -> dict:
    if req.role is not None and req.role not in ROLES:
        raise HTTPException(status_code=422, detail="角色不合法")
    if req.status is not None and req.status not in STATUSES:
        raise HTTPException(status_code=422, detail="账号状态不合法")
    current = await repository.get_user_by_id(user_id)
    if current is None or current.tenant_id != _tenant(request):
        raise HTTPException(status_code=404, detail="用户不存在")
    if (
        current.role == "admin"
        and ((req.role is not None and req.role != "admin") or req.status == "disabled")
    ):
        admins = [
            u for u in await repository.list_users(current.tenant_id)
            if u.role == "admin" and u.status == "active"
        ]
        if len(admins) <= 1:
            raise HTTPException(status_code=409, detail="不能停用或降级最后一个管理员")
    phone = _phone(req.phone) if req.phone is not None else None
    try:
        updated = await repository.update_managed_user(
            user_id, _tenant(request), display_name=req.display_name,
            phone=phone, role=req.role, status=req.status,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="手机号已存在") from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _out(updated)


@router.post("/{user_id}/reset-password")
async def reset_password(user_id: int, req: ResetPasswordRequest, request: Request) -> dict:
    current = await repository.get_user_by_id(user_id)
    if current is None or current.tenant_id != _tenant(request):
        raise HTTPException(status_code=404, detail="用户不存在")
    await repository.update_user_password(user_id, security.hash_password(req.new_password))
    return {"ok": True}
