"""鉴权中间件:auth_enabled 时对 /api/*(除 /api/auth/*)强制 Bearer JWT,并把用户写入 request.state。"""
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.core.security import decode_token


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
            request.state.user = payload
            request.state.tenant_id = payload.get("tenant", "default")
        return await call_next(request)

