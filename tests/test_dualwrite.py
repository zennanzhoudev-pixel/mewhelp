import uuid

import pytest
from pymilvus import MilvusClient

from app.db import repository
from app.kb import dualwrite, milvus_client as mc
from app.kb.documents import Chunk

URI = "http://localhost:19530"


def _milvus_up() -> bool:
    try:
        c = MilvusClient(uri=URI, timeout=3)
        return bool(c.list_collections() is not None)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _milvus_up(), reason="Milvus Standalone 不可用")


def _chunk(q, a):
    return Chunk(
        category="c",
        questions=q,
        answer=a,
        section_path="c / " + q,
        content_type="policy",
    )


async def test_write_pending_links_neighbors(db_session_factory, db_clean):
    ids = await dualwrite.write_pending([_chunk(f"q{i}", f"a{i}") for i in range(3)])
    assert len(ids) == 3
    by_id = {c.id: c for c in await repository.list_pending_chunks()}
    assert by_id[ids[1]].prev_chunk_id == ids[0]
    assert by_id[ids[1]].next_chunk_id == ids[2]
    assert by_id[ids[0]].prev_chunk_id is None


async def test_vectorize_resumes_after_crash(db_session_factory, monkeypatch):
    await dualwrite.write_pending([_chunk(f"q{i}", f"a{i}") for i in range(4)])
    real_calls = {"n": 0}

    async def flaky_embed(texts):
        real_calls["n"] += 1
        if real_calls["n"] == 2:
            raise RuntimeError("嵌入服务中断")
        return [[float(i), 0.0, 1.0] + [0.0] * (1024 - 3) for i, _ in enumerate(texts)]

    monkeypatch.setattr("app.kb.dualwrite.embeddings.embed_texts", flaky_embed)
    client = mc.get_client(uri=URI)
    name = f"test_kb_{uuid.uuid4().hex[:8]}"
    mc.ensure_collection(client, collection=name)
    with pytest.raises(RuntimeError):
        await dualwrite.vectorize_pending(client, batch_size=2, collection=name)
    assert await repository.count_chunks_by_status("done") == 2
    assert await repository.count_chunks_by_status("pending") == 2

    async def ok_embed(texts):
        return [[9.0, 0.0, 1.0] + [0.0] * (1024 - 3) for _ in texts]

    monkeypatch.setattr("app.kb.dualwrite.embeddings.embed_texts", ok_embed)
    done_now = await dualwrite.vectorize_pending(client, batch_size=2, collection=name)
    assert done_now == 2
    assert await repository.count_chunks_by_status("pending") == 0
    assert await repository.count_chunks_by_status("done") == 4
    assert mc.count(client, collection=name) == 4
    mc.drop(client, name)

