"""顾客转人工与客服工作台 API。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.deps import require_roles
from app.db import repository

router = APIRouter(prefix="/api/support")


class TransferRequest(BaseModel):
    conversation_id: int
    reason: str = Field(default="用户主动转人工", max_length=300)


class ReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", None) or "default"


def _identity(request: Request) -> dict:
    return getattr(request.state, "user", None) or {
        "sub": "0", "tenant": "default", "roles": ["admin"],
    }


def _uid(request: Request) -> int:
    try:
        return int(_identity(request).get("sub", 0))
    except (TypeError, ValueError):
        return 0


async def _customer_conversation(request: Request, conversation_id: int):
    conv = await repository.get_conversation(conversation_id, _tenant(request))
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    roles = _identity(request).get("roles", [])
    if "customer" in roles and str(conv.user_id) != str(_uid(request)):
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.post("/request", dependencies=[Depends(require_roles("customer", "admin"))])
async def request_support(req: TransferRequest, request: Request) -> dict:
    await _customer_conversation(request, req.conversation_id)
    out = await repository.request_human_support(
        req.conversation_id, _tenant(request), req.reason
    )
    if out is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return out


@router.get("/{conversation_id}/status",
            dependencies=[Depends(require_roles("customer", "agent", "admin"))])
async def support_status(conversation_id: int, request: Request) -> dict:
    conv = await _customer_conversation(request, conversation_id)
    agent = None
    if conv.assigned_agent_id:
        u = await repository.get_user_by_id(conv.assigned_agent_id)
        if u is not None:
            agent = u.display_name or u.username
    return {
        "conversation_id": conv.id,
        "status": conv.status,
        "assigned_agent_id": conv.assigned_agent_id,
        "agent_name": agent,
        "reason": conv.transfer_reason,
    }


@router.get("/{conversation_id}/messages",
            dependencies=[Depends(require_roles("customer", "agent", "admin"))])
async def support_messages(
    conversation_id: int, request: Request, after_id: int = 0,
) -> dict:
    await _customer_conversation(request, conversation_id)
    rows = await repository.list_support_messages(
        conversation_id, _tenant(request), after_id
    )
    if rows is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"items": rows}


@router.get("/workspace/queue",
            dependencies=[Depends(require_roles("agent", "admin"))])
async def workspace_queue(request: Request, mine: bool = False) -> dict:
    rows = await repository.list_support_queue(
        _tenant(request), assigned_agent_id=_uid(request) if mine else None
    )
    return {
        "items": rows,
        "waiting": sum(1 for r in rows if r["assigned_agent_id"] is None),
        "mine": sum(1 for r in rows if r["assigned_agent_id"] == _uid(request)),
    }


@router.post("/workspace/{conversation_id}/claim",
             dependencies=[Depends(require_roles("agent", "admin"))])
async def claim(conversation_id: int, request: Request) -> dict:
    out = await repository.claim_support(conversation_id, _tenant(request), _uid(request))
    if out is None:
        raise HTTPException(status_code=409, detail="会话已被其他客服认领或不在排队中")
    return out


@router.post("/workspace/{conversation_id}/reply",
             dependencies=[Depends(require_roles("agent", "admin"))])
async def reply(conversation_id: int, req: ReplyRequest, request: Request) -> dict:
    out = await repository.reply_support(
        conversation_id, _tenant(request), _uid(request), req.content.strip()
    )
    if out is None:
        raise HTTPException(status_code=409, detail="请先认领会话后再回复")
    return out


@router.post("/workspace/{conversation_id}/release",
             dependencies=[Depends(require_roles("agent", "admin"))])
async def release(conversation_id: int, request: Request) -> dict:
    if not await repository.release_support(
        conversation_id, _tenant(request), _uid(request)
    ):
        raise HTTPException(status_code=409, detail="只能释放自己认领的会话")
    return {"ok": True}


@router.post("/workspace/{conversation_id}/close",
             dependencies=[Depends(require_roles("agent", "admin"))])
async def close(conversation_id: int, request: Request) -> dict:
    if not await repository.close_support(
        conversation_id, _tenant(request), _uid(request)
    ):
        raise HTTPException(status_code=409, detail="只能结束自己认领的会话")
    return {"ok": True}
