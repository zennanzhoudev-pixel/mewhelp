"""ch07 验收配套:会话列表 + 历史消息回载(只读,前端多会话切换用)。"""
from fastapi import APIRouter, HTTPException, Request

from app.core.access import can_access_conversation, user_id as identity_user_id
from app.db import repository

router = APIRouter()


@router.get("/api/conversations")
async def list_conversations(user_id: str, request: Request):
    tenant_id = getattr(request.state, "tenant_id", None) or "default"
    effective_user_id = identity_user_id(request) or user_id
    items = await repository.list_conversations(effective_user_id, tenant_id=tenant_id)
    return {"items": items}


@router.get("/api/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: int, request: Request):
    tenant_id = getattr(request.state, "tenant_id", None) or "default"
    conv = await repository.get_conversation(conversation_id, tenant_id)
    if conv is None or not can_access_conversation(request, conv):
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = await repository.list_dialog_messages(conversation_id)
    return {"items": [
        {"id": m.id, "role": m.role, "content": m.content or "",
         "sender_type": m.sender_type or "ai", "sender_id": m.sender_id,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in msgs
    ]}
