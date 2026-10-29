import json
import logging
import pathlib

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal

from app.db import repository

logger = logging.getLogger(__name__)
router = APIRouter()

_REPORT = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "data"
    / "ch04"
    / "reports"
    / "rag_eval.json"
)


class FaithCaseStatusRequest(BaseModel):
    status: Literal["未解决", "已解决", "无需解决"]
    resolution: str = Field(default="", description="标已解决/无需解决时必填")


def _load_report() -> dict | None:
    if not _REPORT.exists():
        return None
    try:
        return json.loads(_REPORT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


@router.get("/api/rag-eval/overview")
async def overview():
    report = _load_report()
    if report is None:
        return {"present": False, "job": "eval-rag"}
    retrieval = report.get("retrieval") or {}
    best = None
    best_mrr = -1.0
    # retrieval 形如 {bucket: {strategy: {mrr, recall_at_k}}}
    for bucket, strategies in retrieval.items():
        if not isinstance(strategies, dict):
            continue
        for strategy, metrics in strategies.items():
            if not isinstance(metrics, dict):
                continue
            mrr = metrics.get("mrr")
            if isinstance(mrr, (int, float)) and mrr > best_mrr:
                best_mrr = mrr
                best = strategy
    generation = report.get("generation")
    return {
        "present": True,
        "meta": report.get("meta"),
        "retrieval": retrieval,
        "evidence_coverage": report.get("evidence_coverage"),
        "generation": generation,
        "generation_done": generation is not None,
        "best": best,
        "job": "eval-rag",
    }


@router.get("/api/rag-eval/faith-cases")
async def faith_cases(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    try:
        rows, total, counts = await repository.list_faith_cases(status, page, size)
    except Exception:
        raise HTTPException(status_code=503, detail="数据库暂时不可用,请稍后重试")
    return {
        "items": [
            {
                "id": r.id,
                "eval_id": r.eval_id,
                "bucket": r.bucket,
                "query": r.query,
                "strategy": r.strategy,
                "answer": r.answer,
                "reason": r.reason,
                "citations": r.citations,
                "judge_model": r.judge_model,
                "status": r.status,
                "seen_count": r.seen_count,
                "resolution": r.resolution,
                "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
                "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
            }
            for r in rows
        ],
        "total": total,
        "counts": counts,
        "page": page,
        "size": size,
    }


@router.post("/api/rag-eval/faith-cases/{faith_id}/status")
async def set_faith_case_status(faith_id: int, req: FaithCaseStatusRequest):
    if req.status != "未解决" and not req.resolution.strip():
        raise HTTPException(status_code=400, detail="标已解决/无需解决时,处置说明必填")
    try:
        await repository.set_faith_case_status(faith_id, req.status, req.resolution or None)
    except Exception:
        raise HTTPException(status_code=503, detail="数据库暂时不可用,请稍后重试")
    return {"ok": True}

