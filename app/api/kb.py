import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.db import repository
from app.kb import dedup, documents, dualwrite, milvus_client, sources
from app.core import retrieval

logger = logging.getLogger(__name__)
router = APIRouter()


class PreviewRequest(BaseModel):
    content_type: str = Field(description="内容类型:faq / policy / manual / spec")
    text: str = Field(min_length=1, description="要切块的 Markdown 正文")


class IngestRequest(BaseModel):
    content_type: str = Field(description="内容类型:faq / policy / manual / spec")
    text: str = Field(min_length=1, description="要入库的 Markdown 正文")
    vectorize: bool = Field(default=False, description="入库后顺手向量化")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, description="检索问句")
    strategy: str = Field(default="hybrid_rerank", description="vector/bm25/hybrid/hybrid_rerank")
    top_k: int = Field(default=10, ge=1, le=50)


def _fingerprint(c) -> str:
    return f"{dedup.normalize_question(c.questions)}|{dedup.normalize_question(c.answer)}"


def _chunk_view(c, duplicate: bool = False) -> dict:
    return {
        "category": c.category,
        "questions": c.questions,
        "answer": c.answer,
        "section_path": c.section_path,
        "content_type": c.content_type,
        "is_key_clause": c.is_key_clause,
        "is_table": c.answer.lstrip().startswith("|"),
        "chars": len(c.answer),
        "duplicate": duplicate,
    }


@router.get("/api/kb/overview")
async def overview():
    try:
        stats = await repository.knowledge_stats()
    except SQLAlchemyError:
        stats = {"total": None, "pending": None, "done": None, "key_clauses": None}
    try:
        client = milvus_client.get_client()
        milvus_count = milvus_client.count(client)
        consistent = (
            None if stats.get("done") is None else (stats["done"] == milvus_count)
        )
    except Exception:
        milvus_count = None
        consistent = None
    try:
        staging = await repository.staging_stats()
    except SQLAlchemyError:
        staging = {}
    return {
        "knowledge": stats,
        "milvus_count": milvus_count,
        "consistent": consistent,
        "staging": staging,
        "sources": list(sources.SOURCE_TYPES.keys()),
    }


@router.post("/api/kb/preview")
async def preview(req: PreviewRequest):
    if req.content_type not in sources.CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"非法 content_type:{req.content_type}")
    chunks = documents.build_chunks(req.text, content_type=req.content_type)
    try:
        existing = {_fingerprint(c) for c in await repository.list_chunk_pairs()}
    except SQLAlchemyError:
        existing = set()
    return {
        "chunks": [_chunk_view(c, _fingerprint(c) in existing) for c in chunks],
        "total": len(chunks),
    }


@router.post("/api/kb/ingest")
async def ingest(req: IngestRequest):
    if req.content_type not in sources.CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"非法 content_type:{req.content_type}")
    chunks = documents.build_chunks(req.text, content_type=req.content_type)
    try:
        existing = {_fingerprint(c) for c in await repository.list_chunk_pairs()}
        kept = [c for c in chunks if _fingerprint(c) not in existing]
    except SQLAlchemyError:
        kept = list(chunks)
    try:
        await dualwrite.write_pending(kept)
    except SQLAlchemyError as exc:
        logger.exception("知识入库失败")
        raise HTTPException(status_code=503, detail="数据库暂时不可用,请稍后重试") from exc
    vectorized = 0
    if req.vectorize and kept:
        try:
            client = milvus_client.get_client()
            milvus_client.ensure_collection(client)
            vectorized = await dualwrite.vectorize_pending(client)
        except Exception as exc:
            logger.exception("向量化失败(已入库,pending 可补跑)")
            raise HTTPException(
                status_code=502,
                detail=f"已入库 {len(kept)} 块(pending),补跑一次即可",
            ) from exc
    return {
        "inserted": len(kept),
        "skipped": len(chunks) - len(kept),
        "vectorized": vectorized,
    }


@router.post("/api/kb/vectorize")
async def vectorize():
    try:
        client = milvus_client.get_client()
        milvus_client.ensure_collection(client)
        done = await dualwrite.vectorize_pending(client)
        return {"vectorized": done, "milvus_count": milvus_client.count(client)}
    except Exception as exc:
        logger.exception("向量化失败")
        raise HTTPException(status_code=502, detail="向量化失败,请查看日志并补跑") from exc


@router.post("/api/kb/search")
async def search(req: SearchRequest):
    if req.strategy not in ("vector", "bm25", "hybrid", "hybrid_rerank"):
        raise HTTPException(status_code=400, detail=f"非法 strategy:{req.strategy}")
    try:
        hits = await retrieval.search_knowledge(
            req.query, strategy=req.strategy, top_k=req.top_k
        )
        return {"hits": hits}
    except Exception as exc:
        logger.exception("检索自测失败")
        raise HTTPException(status_code=502, detail="检索失败,请确认 Milvus 与嵌入上游可用") from exc


@router.get("/api/kb/staging")
async def staging():
    try:
        stats = await repository.staging_stats()
        rows = await repository.list_staging_by_status("extracted")
    except SQLAlchemyError:
        stats, rows = {}, []
    return {
        "stats": stats,
        "extracted": [
            {
                "id": r.id,
                "batch_no": r.batch_no,
                "source_ref": r.source_ref,
                "question": r.question,
                "answer": r.answer,
            }
            for r in rows
        ],
    }

