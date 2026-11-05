"""会话级访问控制:顾客只能访问自己的会话,客服/管理员可按租户处理。"""
from fastapi import Request


def identity(request: Request) -> dict | None:
    return getattr(request.state, "user", None)


def user_id(request: Request) -> str | None:
    me = identity(request)
    return str(me["sub"]) if me and me.get("sub") is not None else None


def roles(request: Request) -> set[str]:
    me = identity(request)
    return set((me or {}).get("roles") or [])


def is_staff(request: Request) -> bool:
    return bool(roles(request) & {"admin", "agent"})


def can_access_conversation(request: Request, conversation) -> bool:
    """鉴权关闭时保持本地兼容;鉴权开启时 staff 看租户内,顾客只看自己。"""
    if identity(request) is None:
        return True
    if is_staff(request):
        return True
    return str(conversation.user_id) == user_id(request)
