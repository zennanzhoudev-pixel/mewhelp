"""登录、注册、手机号验证码、二维码确认和当前账号。"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import segno
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import settings
from app.core import security, sms
from app.db import repository

router = APIRouter()

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    tenant_id: str = Field(default="default", min_length=1, max_length=64)
    phone: str | None = None
    display_name: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: int
    username: str
    display_name: str | None
    phone: str | None
    role: str
    tenant_id: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class SmsSendRequest(BaseModel):
    phone: str


class SmsLoginRequest(BaseModel):
    phone: str
    code: str = Field(min_length=6, max_length=6)


def _normalize_phone(phone: str) -> str:
    value = re.sub(r"[\s-]", "", phone or "")
    if not PHONE_RE.fullmatch(value):
        raise HTTPException(status_code=422, detail="请输入有效的 11 位手机号")
    return value


def _user_payload(u) -> TokenResponse:
    return TokenResponse(
        token=security.create_token(u.id, u.tenant_id, [u.role]),
        user_id=u.id,
        username=u.username,
        display_name=u.display_name,
        phone=u.phone,
        role=u.role,
        tenant_id=u.tenant_id,
    )


def _ensure_active(u) -> None:
    if u is None:
        raise HTTPException(status_code=401, detail="账号或凭证错误")
    if (getattr(u, "status", "active") or "active") != "active":
        raise HTTPException(status_code=403, detail="账号已停用")


def _code_hash(phone: str, code: str) -> str:
    key = (settings.jwt_secret or "mewhelp-local-otp").encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def _public_base(request: Request) -> str:
    if not settings.public_base_url:
        return str(request.base_url).rstrip("/")
    configured = settings.public_base_url.rstrip("/")
    parts = urlsplit(configured)
    try:
        private_target = ipaddress.ip_address(parts.hostname or "").is_private
    except ValueError:
        private_target = parts.hostname in {"localhost", "127.0.0.1"}
    local_request = request.url.hostname in {"localhost", "127.0.0.1", "::1"}
    if private_target and local_request and request.url.port:
        # 本地常同时跑 8000/8001 验证端口;二维码主机保留局域网 IP,端口跟随当前页面。
        netloc = f"{parts.hostname}:{request.url.port}"
        configured = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return configured


@router.get("/api/auth/config")
async def auth_config() -> dict:
    return {
        "auth_enabled": settings.auth_enabled,
        "sms_provider": settings.sms_provider,
        "qr_login_enabled": True,
    }


@router.post("/api/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest) -> TokenResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="鉴权未启用")
    if await repository.get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    phone = _normalize_phone(req.phone) if req.phone else None
    if phone and await repository.get_user_by_phone(phone):
        raise HTTPException(status_code=409, detail="手机号已绑定其他账号")
    is_admin_seed = (
        req.username == settings.admin_user
        and bool(settings.admin_password)
        and req.password == settings.admin_password
    )
    role = "admin" if is_admin_seed else "customer"
    uid = await repository.create_managed_user(
        req.username, security.hash_password(req.password), role, req.tenant_id,
        phone=phone, display_name=req.display_name or req.username,
    )
    u = await repository.get_user_by_id(uid)
    _ensure_active(u)
    await repository.touch_user_login(u.id)
    return _user_payload(u)


@router.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    u = await repository.get_user_by_username(req.username)
    if u is None or not security.verify_password(req.password, u.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    _ensure_active(u)
    await repository.touch_user_login(u.id)
    return _user_payload(u)


@router.post("/api/auth/sms/send")
async def send_sms_code(req: SmsSendRequest) -> dict:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="鉴权未启用")
    phone = _normalize_phone(req.phone)
    u = await repository.get_user_by_phone(phone)
    if u is not None:
        _ensure_active(u)
    latest = await repository.latest_login_code(phone)
    now = datetime.now()
    if latest and latest.created_at and (now - latest.created_at).total_seconds() < settings.sms_resend_seconds:
        wait = max(1, settings.sms_resend_seconds - int((now - latest.created_at).total_seconds()))
        raise HTTPException(status_code=429, detail=f"请 {wait} 秒后再试")
    code = f"{secrets.randbelow(1_000_000):06d}"
    await repository.create_login_code(
        phone, _code_hash(phone, code), now + timedelta(seconds=settings.sms_code_ttl_seconds)
    )
    try:
        await sms.send_login_code(phone, code)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="短信发送服务暂时不可用") from exc
    out = {"ok": True, "expires_in": settings.sms_code_ttl_seconds}
    if settings.sms_debug_return_code:
        out["debug_code"] = code
    return out


@router.post("/api/auth/sms/login", response_model=TokenResponse)
async def sms_login(req: SmsLoginRequest) -> TokenResponse:
    phone = _normalize_phone(req.phone)
    row = await repository.latest_login_code(phone)
    if row is None or row.used_at is not None or row.expires_at <= datetime.now():
        raise HTTPException(status_code=401, detail="验证码已失效")
    if row.attempts >= 5:
        raise HTTPException(status_code=429, detail="验证码尝试次数过多")
    if not hmac.compare_digest(row.code_hash, _code_hash(phone, req.code)):
        await repository.update_login_code(row, attempts=row.attempts + 1)
        raise HTTPException(status_code=401, detail="验证码错误")
    u = await repository.get_user_by_phone(phone)
    if u is None:
        username = f"phone_{phone}"
        if await repository.get_user_by_username(username):
            username = f"{username}_{secrets.token_hex(3)}"
        uid = await repository.create_managed_user(
            username,
            security.hash_password(secrets.token_urlsafe(32)),
            "customer",
            "default",
            phone=phone,
            display_name=f"用户{phone[-4:]}",
        )
        u = await repository.get_user_by_id(uid)
    _ensure_active(u)
    await repository.update_login_code(row, used_at=datetime.now())
    await repository.touch_user_login(u.id)
    return _user_payload(u)


@router.post("/api/auth/qr/start")
async def qr_start(request: Request) -> dict:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="鉴权未启用")
    ticket = secrets.token_urlsafe(32)
    await repository.create_qr_session(ticket, datetime.now() + timedelta(minutes=2))
    mobile_url = f"{_public_base(request)}/qr/approve?ticket={ticket}"
    return {
        "ticket": ticket,
        "expires_in": 120,
        "mobile_url": mobile_url,
        "qr_svg": f"/api/auth/qr/{ticket}.svg",
    }


@router.get("/api/auth/qr/{ticket}.svg")
async def qr_svg(ticket: str, request: Request) -> Response:
    row = await repository.get_qr_session(ticket)
    if row is None:
        raise HTTPException(status_code=404, detail="二维码不存在")
    mobile_url = f"{_public_base(request)}/qr/approve?ticket={ticket}"
    svg = segno.make(mobile_url, error="m").svg_inline(scale=6, border=2)
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@router.get("/api/auth/qr/{ticket}/status")
async def qr_status(ticket: str):
    row, claimed = await repository.consume_qr_session(ticket)
    if row is None:
        raise HTTPException(status_code=404, detail="二维码不存在")
    if row.status == "pending":
        return {"status": "pending"}
    if row.status == "expired":
        return {"status": "expired"}
    if not claimed:
        return {"status": "consumed" if row.status == "consumed" else row.status}
    u = await repository.get_user_by_id(row.user_id)
    _ensure_active(u)
    await repository.touch_user_login(u.id)
    return _user_payload(u)


@router.post("/api/auth/qr/{ticket}/approve")
async def qr_approve(ticket: str, request: Request) -> dict:
    token = (request.headers.get("Authorization", "") or "").removeprefix("Bearer ")
    payload = security.decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="请先登录手机端")
    mobile_user = await repository.get_user_by_id(int(payload["sub"]))
    _ensure_active(mobile_user)
    row = await repository.approve_qr_session(ticket, int(payload["sub"]))
    if row is None:
        raise HTTPException(status_code=409, detail="二维码已失效或已被使用")
    return {"ok": True}


@router.get("/api/auth/me")
async def me(request: Request) -> dict:
    token = (request.headers.get("Authorization", "") or "").removeprefix("Bearer ")
    payload = security.decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="凭证无效或已过期")
    u = await repository.get_user_by_id(int(payload["sub"]))
    _ensure_active(u)
    return {
        "user_id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "phone": u.phone,
        "tenant_id": u.tenant_id,
        "roles": [u.role],
        "role": u.role,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


@router.post("/api/auth/change-password")
async def change_password(req: ChangePasswordRequest, request: Request) -> dict:
    token = (request.headers.get("Authorization", "") or "").removeprefix("Bearer ")
    payload = security.decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="凭证无效或已过期")
    user = await repository.get_user_by_id(int(payload["sub"]))
    if user is None or not security.verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=401, detail="旧密码错误")
    await repository.update_user_password(user.id, security.hash_password(req.new_password))
    return {"ok": True}
