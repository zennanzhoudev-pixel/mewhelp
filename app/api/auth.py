"""注册 / 登录 / 我。仅在 auth_enabled 时启用;密码 PBKDF2 散列,签发 JWT。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core import security
from app.db import repository

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    tenant_id: str = Field(default="default", min_length=1, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    role: str
    tenant_id: str


def _issue(user_id: int, tenant_id: str, role: str) -> TokenResponse:
    return TokenResponse(
        token=security.create_token(user_id, tenant_id, [role]),
        role=role,
        tenant_id=tenant_id,
    )


@router.post("/api/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest) -> TokenResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="鉴权未启用")
    if await repository.get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    # 首个管理员种子:用户名与密码匹配 settings.admin_user/admin_password 时授予 admin
    role = (
        "admin"
        if (req.username == settings.admin_user and req.password == settings.admin_password)
        else "viewer"
    )
    uid = await repository.create_user(
        req.username, security.hash_password(req.password), role, req.tenant_id
    )
    return _issue(uid, req.tenant_id, role)


@router.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    u = await repository.get_user_by_username(req.username)
    if not u or not security.verify_password(req.password, u.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _issue(u.id, u.tenant_id, u.role)


@router.get("/api/auth/me")
async def me(authorization: str | None = None) -> dict:
    token = (authorization or "").removeprefix("Bearer ")
    payload = security.decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="凭证无效或已过期")
    return {
        "user_id": int(payload["sub"]),
        "tenant_id": payload.get("tenant", "default"),
        "roles": payload.get("roles", []),
    }

