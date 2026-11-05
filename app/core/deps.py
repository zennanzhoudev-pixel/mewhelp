"""RBAC 依赖:从中间件写入的 request.state.user 取角色做鉴权。"""
from fastapi import HTTPException, Request


def require_roles(*roles: str):
    async def dep(request: Request) -> dict:
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(status_code=401, detail="未登录")
        if roles and not set(roles) & set(user.get("roles", [])):
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return dep

