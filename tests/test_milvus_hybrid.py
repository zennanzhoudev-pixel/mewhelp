import time
import uuid

import pytest
from pymilvus import MilvusClient

from app.kb import milvus_client as mc

URI = "http://localhost:19530"


def _milvus_up() -> bool:
    try:
        c = MilvusClient(uri=URI, timeout=3)
        return bool(c.list_collections() is not None)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _milvus_up(), reason="Milvus Standalone 不可用(需 make milvus-up)")


@pytest.fixture()
def coll():
    client = mc.get_client(uri=URI)
    name = f"test_kb_{uuid.uuid4().hex[:8]}"
    mc.ensure_collection(client, collection=name)
    rows = [
        {
            "id": 1,
            "dense": [0.1] * 1024,
            "text": "运费 满99元包邮 不满10元",
            "question": "运费怎么算",
            "answer": "满99包邮,否则10元",
            "section_path": "运费政策",
            "content_type": "faq",
            "category": "运费",
        },
        {
            "id": 2,
            "dense": [0.2] * 1024,
            "text": "智能猫砂盆 Pro 型号 自动清理",
            "question": "Pro 型号功能",
            "answer": "自动清理除臭",
            "section_path": "商品手册 / 猫砂盆",
            "content_type": "manual",
            "category": "商品手册",
        },
    ]
    mc.upsert_vectors(client, rows, collection=name)
    mc.flush(client, collection=name)
    client.load_collection(name)
    time.sleep(2)
    yield client, name
    mc.drop(client, name)


def test_bm25_hits_model_number(coll):
    client, name = coll
    hits = mc.bm25_search(client, "猫砂盆 Pro 型号", top_k=2, collection=name)
    assert hits[0]["id"] == 2
    assert hits[0]["section_path"] == "商品手册 / 猫砂盆"


def test_hybrid_returns_scored_hits(coll):
    client, name = coll
    hits = mc.hybrid_search(client, [0.1] * 1024, "运费", top_k=2, recall=10, collection=name)
    assert hits
    assert {"id", "score", "question", "answer", "section_path", "content_type", "category"} <= hits[0].keys()


def test_category_filter(coll):
    client, name = coll
    hits = mc.bm25_search(client, "型号 运费", top_k=5, category="运费", collection=name)
    assert all(h["category"] == "运费" for h in hits)

