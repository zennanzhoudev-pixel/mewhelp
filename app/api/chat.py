import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.access import can_access_conversation
from app.db import repository
from app.graph import runtime
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_error(message: str) -> AsyncIterator[str]:
    yield "event: error\n"
    yield _sse({"message": message})


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    tenant_id = getattr(request.state, "tenant_id", None) or "default"
    identity = getattr(request.state, "user", None)
    user_id = str(identity["sub"]) if identity else req.user_id

    async def event_stream() -> AsyncIterator[str]:
        try:
            if identity is not None and req.conversation_id is not None:
                conv = await repository.get_conversation(req.conversation_id, tenant_id)
                if conv is None or not can_access_conversation(request, conv):
                    raise runtime.ConversationNotFound(req.conversation_id)
                if conv.status == "已转人工":
                    await repository.append_message(
                        conv.id, "user", content=req.message, sender_type="user"
                    )
                    yield _sse({"delta": "消息已发送给人工客服，请稍候。"})
                    yield _sse({"event": "done", "conversation_id": conv.id})
                    yield "data: [DONE]\n\n"
                    return
                if conv.status == "已结束":
                    yield "event: error\n"
                    yield _sse({"message": "会话已结束，请新建会话后继续提问"})
                    return
            async for ev in runtime.stream_turn(
                user_id, req.message, req.conversation_id, tenant_id=tenant_id
            ):
                if ev["type"] == "tool":
                    yield _sse({"event": "tool", "name": ev["name"]})
                elif ev["type"] == "delta":
                    yield _sse({"delta": ev["text"]})
                elif ev["type"] == "citations":
                    yield _sse({"event": "citations", "items": ev["items"]})
                elif ev["type"] == "interrupt":
                    # ch08:负载透传(select_order 带 orders / confirm_ticket 带 preview),前端按 kind 分发
                    yield _sse({"event": "interrupt",
                                **{k: v for k, v in ev.items() if k != "type"}})
                elif ev["type"] == "actions":
                    yield _sse({"event": "actions", "items": ev["items"]})
                elif ev["type"] == "done":
                    yield _sse({"event": "done", "conversation_id": ev["conversation_id"]})
        except runtime.ConversationNotFound:
            for f in _sse_error("会话不存在"):
                yield f
            return
        except SQLAlchemyError:
            logger.exception("数据库错误 user_id=%s", user_id)
            for f in _sse_error("数据库暂时不可用,请稍后重试"):
                yield f
            return
        except Exception:
            logger.exception("图编排失败 user_id=%s", user_id)
            for f in _sse_error("上游模型暂时不可用,请稍后重试"):
                yield f
            return
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
