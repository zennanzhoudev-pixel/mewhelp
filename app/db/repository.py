from datetime import datetime

from sqlalchemy import func, select

import app.db.base as db  # 用模块属性引用,便于测试 monkeypatch async_session
from app.db.models import (
    Conversation,
    FaithCase,
    Faq,
    KnowledgeChunk,
    LowConfidenceQuestion,
    Message,
    QaExtractionStaging,
    Ticket,
)

_TICKET_SEQ = 0


def _gen_ticket_no() -> str:
    global _TICKET_SEQ
    _TICKET_SEQ += 1
    return f"T{datetime.now():%Y%m%d%H%M%S}{_TICKET_SEQ:03d}"


# ============================================================
# ch02:会话 / 消息 / faq / 工单
# ============================================================


async def create_conversation(user_id: str) -> int:
    async with db.async_session() as s:
        conv = Conversation(user_id=user_id)
        s.add(conv)
        await s.commit()
        return conv.id


async def get_conversation(conversation_id: int) -> Conversation | None:
    async with db.async_session() as s:
        return await s.get(Conversation, conversation_id)


async def append_message(
    conversation_id: int,
    role: str,
    content: str | None = None,
    tool_calls: list | None = None,
    tool_call_id: str | None = None,
) -> int:
    async with db.async_session() as s:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
        )
        s.add(msg)
        await s.commit()
        return msg.id


async def list_messages(conversation_id: int) -> list[Message]:
    async with db.async_session() as s:
        result = await s.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )
        return list(result.scalars())


async def search_faq(keyword: str) -> list[Faq]:
    async with db.async_session() as s:
        result = await s.execute(select(Faq).where(Faq.question.like(f"%{keyword}%")))
        return list(result.scalars())


async def create_ticket(conversation_id: int, description: str, ticket_type: str) -> str:
    ticket_no = _gen_ticket_no()
    async with db.async_session() as s:
        s.add(
            Ticket(
                ticket_no=ticket_no,
                conversation_id=conversation_id,
                description=description,
                ticket_type=ticket_type,
            )
        )
        conv = await s.get(Conversation, conversation_id)
        if conv is not None:
            conv.status = "已转人工"
        await s.commit()
    return ticket_no


# ============================================================
# ch03:知识 chunk / 暂存表
# ============================================================


async def insert_knowledge_chunk(
    category: str,
    questions: str,
    answer: str,
    section_path: str | None = None,
    content_type: str | None = None,
    is_key_clause: int = 0,
) -> int:
    async with db.async_session() as s:
        row = KnowledgeChunk(
            category=category,
            questions=questions,
            answer=answer,
            section_path=section_path,
            content_type=content_type,
            is_key_clause=is_key_clause,
        )
        s.add(row)
        await s.commit()
        return row.id


async def list_pending_chunks() -> list[KnowledgeChunk]:
    async with db.async_session() as s:
        result = await s.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.vectorize_status == "pending")
            .order_by(KnowledgeChunk.id)
        )
        return list(result.scalars())


async def mark_chunk_vectorized(chunk_id: int, vector_id: str) -> None:
    async with db.async_session() as s:
        row = await s.get(KnowledgeChunk, chunk_id)
        if row is not None:
            row.vector_id = vector_id
            row.vectorize_status = "done"
            await s.commit()


async def set_chunk_neighbors(
    chunk_id: int, prev_id: int | None, next_id: int | None
) -> None:
    async with db.async_session() as s:
        row = await s.get(KnowledgeChunk, chunk_id)
        if row is not None:
            row.prev_chunk_id = prev_id
            row.next_chunk_id = next_id
            await s.commit()


async def count_chunks_by_status(status: str) -> int:
    async with db.async_session() as s:
        result = await s.execute(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.vectorize_status == status)
        )
        return int(result.scalar_one())


async def list_all_questions() -> list[str]:
    async with db.async_session() as s:
        result = await s.execute(select(KnowledgeChunk.questions))
        return list(result.scalars())


async def insert_staging(
    batch_no: str, source_ref: str | None, question: str, answer: str
) -> int:
    async with db.async_session() as s:
        row = QaExtractionStaging(
            batch_no=batch_no, source_ref=source_ref, question=question, answer=answer
        )
        s.add(row)
        await s.commit()
        return row.id


async def list_staging_by_status(status: str) -> list[QaExtractionStaging]:
    async with db.async_session() as s:
        result = await s.execute(
            select(QaExtractionStaging)
            .where(QaExtractionStaging.status == status)
            .order_by(QaExtractionStaging.id)
        )
        return list(result.scalars())


async def set_staging_status(ids: list[int], status: str) -> None:
    if not ids:
        return
    async with db.async_session() as s:
        for i in ids:
            row = await s.get(QaExtractionStaging, i)
            if row is not None:
                row.status = status
        await s.commit()


async def list_conversations_with_messages() -> list[tuple[int, list[Message]]]:
    async with db.async_session() as s:
        conv_ids = list(
            (await s.execute(select(Conversation.id).order_by(Conversation.id))).scalars()
        )
        out: list[tuple[int, list[Message]]] = []
        for cid in conv_ids:
            msgs = list(
                (
                    await s.execute(
                        select(Message)
                        .where(Message.conversation_id == cid)
                        .order_by(Message.id)
                    )
                ).scalars()
            )
            out.append((cid, msgs))
        return out


async def knowledge_stats() -> dict:
    async with db.async_session() as s:
        total = int(
            (await s.execute(select(func.count()).select_from(KnowledgeChunk))).scalar_one()
        )
        pending = await count_chunks_by_status("pending")
        done = await count_chunks_by_status("done")
        key = int(
            (
                await s.execute(
                    select(func.count())
                    .select_from(KnowledgeChunk)
                    .where(KnowledgeChunk.is_key_clause == 1)
                )
            ).scalar_one()
        )
        return {"total": total, "pending": pending, "done": done, "key_clauses": key}


async def list_recent_chunks(limit: int = 10) -> list[KnowledgeChunk]:
    async with db.async_session() as s:
        result = await s.execute(
            select(KnowledgeChunk).order_by(KnowledgeChunk.id.desc()).limit(limit)
        )
        return list(result.scalars())


async def list_chunk_pairs() -> list[tuple[str, str]]:
    """返回已有 chunk 的 (questions, answer),供录入页按「问法 + 正文」指纹查重。"""
    async with db.async_session() as s:
        result = await s.execute(select(KnowledgeChunk.questions, KnowledgeChunk.answer))
        return [(q, a) for q, a in result.all()]


async def staging_stats() -> dict:
    async with db.async_session() as s:
        extracted = len(await list_staging_by_status("extracted"))
        kept = len(await list_staging_by_status("kept"))
        discarded = len(await list_staging_by_status("discarded"))
        batches = len(
            set(
                (
                    await s.execute(select(QaExtractionStaging.batch_no).distinct())
                ).scalars()
            )
        )
        return {
            "extracted": extracted,
            "kept": kept,
            "discarded": discarded,
            "batches": batches,
        }


# ============================================================
# ch04:低置信问题池 / 编造个案台账
# ============================================================


async def insert_low_confidence(
    conversation_id: int | None, raw_question: str, source: str, reason: str | None
) -> int:
    async with db.async_session() as s:
        row = LowConfidenceQuestion(
            conversation_id=conversation_id,
            raw_question=raw_question,
            source=source,
            reason=reason,
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row.id


async def upsert_faith_case(
    eval_id: str,
    bucket: str,
    query: str,
    strategy: str,
    answer: str,
    reason: str,
    citations: list | None,
    judge_model: str | None,
) -> tuple[bool, bool]:
    """按 eval_id 一题一行;重复判编造只更新快照并累加次数。
    已处置过的题再被判出,退回「未解决」并返回复发标记。"""
    async with db.async_session() as s:
        row = (
            await s.execute(select(FaithCase).where(FaithCase.eval_id == eval_id))
        ).scalar_one_or_none()
        if row is None:
            row = FaithCase(
                eval_id=eval_id,
                bucket=bucket,
                query=query,
                strategy=strategy,
                answer=answer,
                reason=reason,
                citations=citations,
                judge_model=judge_model,
            )
            s.add(row)
            await s.commit()
            return True, False
        relapse = row.status != "未解决"
        row.bucket = bucket
        row.query = query
        row.strategy = strategy
        row.answer = answer
        row.reason = reason
        row.citations = citations
        row.judge_model = judge_model
        row.seen_count = (row.seen_count or 1) + 1
        row.last_seen_at = func.now()
        if relapse:
            row.status = "未解决"
            row.resolution = None
        await s.commit()
        return False, relapse


async def list_faith_cases(
    status: str | None = None, page: int = 1, size: int = 20
) -> tuple[list[FaithCase], int, dict[str, int]]:
    async with db.async_session() as s:
        base = select(FaithCase)
        if status:
            base = base.where(FaithCase.status == status)
        total = int(
            (await s.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        )
        rows = (
            await s.execute(
                base.order_by(FaithCase.last_seen_at.desc()).offset((page - 1) * size).limit(size)
            )
        ).scalars()
        counts: dict[str, int] = {}
        for st in ("未解决", "已解决", "无需解决"):
            counts[st] = int(
                (
                    await s.execute(
                        select(func.count())
                        .select_from(FaithCase)
                        .where(FaithCase.status == st)
                    )
                ).scalar_one()
            )
        return list(rows), total, counts


async def set_faith_case_status(
    faith_id: int, status: str, resolution: str | None
) -> None:
    async with db.async_session() as s:
        row = await s.get(FaithCase, faith_id)
        if row is not None:
            row.status = status
            if status == "未解决":
                row.resolution = None
                row.resolved_at = None
            else:
                row.resolution = resolution
                row.resolved_at = func.now()
            await s.commit()


async def faith_case_status_map() -> dict[str, str]:
    async with db.async_session() as s:
        rows = (await s.execute(select(FaithCase.eval_id, FaithCase.status))).all()
        return {eval_id: status for eval_id, status in rows}

