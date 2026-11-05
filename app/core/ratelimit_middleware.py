"""限流中间件:按客户端 IP 计数,超限返回 429。"""
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.ratelimit import check_rate


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.client.host if request.client else "unknown"
        if not await check_rate(key):
            return JSONResponse({"detail": "请求过于频繁,请稍后再试"}, status_code=429)
        return await call_next(request)

