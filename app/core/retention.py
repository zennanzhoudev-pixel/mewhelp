"""数据保留期清理:按 created_at 删除过期数据(依赖顺序先子后父)。"""
from datetime import datetime, timedelta

from sqlalchemy import text

import app.db.base as db
from app.config import settings


async def run_retention() -> dict:
    done: dict[str, int] = {}
    async with db.async_session() as s:
        await s.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        try:
            if settings.retention_days_audit:
                done["tool_audit_logs"] = await _delete(s, "tool_audit_logs", settings.retention_days_audit)
            if settings.retention_days_low_conf:
                done["low_confidence_questions"] = await _delete(s, "low_confidence_questions", settings.retention_days_low_conf)
            if settings.retention_days_conversations:
                done["messages"] = await _delete(s, "messages", settings.retention_days_conversations)
                done["conversations"] = await _delete(s, "conversations", settings.retention_days_conversations)
        finally:
            await s.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        await s.commit()
    return done


async def _delete(session, table: str, days: int) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    r = await session.execute(text(f"DELETE FROM {table} WHERE created_at < :c"), {"c": cutoff})
    return r.rowcount or 0

