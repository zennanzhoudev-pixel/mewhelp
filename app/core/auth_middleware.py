"""鉴权中间件:auth_enabled 时对 /api/*(除 /api/auth/*)强制 Bearer JWT,并把用户写入 request.state。"""
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.core.security import decode_token
from app.db import repository


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            settings.auth_enabled
            and path.startswith("/api/")
            and not path.startswith("/api/auth/")
        ):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return JSONResponse({"detail": "未登录"}, status_code=401)
            payload = decode_token(auth[7:])
            if not payload:
                return JSONResponse({"detail": "凭证无效或已过期"}, status_code=401)
            try:
                user = await repository.get_user_by_id(int(payload["sub"]))
            except (KeyError, TypeError, ValueError):
                user = None
            if user is None:
                return JSONResponse({"detail": "账号不存在"}, status_code=401)
            if (user.status or "active") != "active":
                return JSONResponse({"detail": "账号已停用"}, status_code=403)
            # 角色和租户以数据库当前值为准,管理员改角色后立即生效,不必等 JWT 过期。
            payload["roles"] = [user.role]
            payload["tenant"] = user.tenant_id
            request.state.user = payload
            request.state.tenant_id = payload.get("tenant", "default")
        return await call_next(request)

