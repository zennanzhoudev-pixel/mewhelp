"""RBAC 依赖:从中间件写入的 request.state.user 取角色做鉴权。"""
from fastapi import HTTPException, Request

from app.config import settings


def require_roles(*roles: str):
    async def dep(request: Request) -> dict:
        # 本地兼容模式:显式关闭鉴权时所有接口按内置管理员运行。
        # 一旦 AUTH_ENABLED=true,这里必须 fail closed,不能靠 HTTP 方法或页面 URL 兜底。
        if not settings.auth_enabled:
            return {"roles": ["admin"], "tenant": "default", "sub": "0"}
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(status_code=401, detail="未登录")
        if roles and not set(roles) & set(user.get("roles", [])):
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return dep


async def require_admin(request: Request) -> dict:
    """后台管理固定角色依赖,供各管理路由统一复用。"""
    return await require_roles("admin")(request)

