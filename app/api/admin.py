from fastapi import APIRouter

from app.db import repository
from app.kb import milvus_client

router = APIRouter()


@router.get("/api/admin/overview")
async def overview():
    cards = {}
    try:
        cards["knowledge"] = {
            "ok": True,
            "stats": await repository.knowledge_stats(),
            "milvus_count": milvus_client.count(milvus_client.get_client()),
        }
    except Exception:
        cards["knowledge"] = {"ok": False}
    try:
        cards["staging"] = {"ok": True, "stats": await repository.staging_stats()}
    except Exception:
        cards["staging"] = {"ok": False}
    return {"cards": cards}

