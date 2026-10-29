import json

from fastapi.testclient import TestClient

from app.api import rageval
from app.main import app


def _report(tmp_path, monkeypatch, payload):
    f = tmp_path / "rag_eval.json"
    f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(rageval, "_REPORT", f)
    return TestClient(app)


def test_missing_report_present_false(tmp_path, monkeypatch):
    monkeypatch.setattr(rageval, "_REPORT", tmp_path / "nope.json")
    client = TestClient(app)
    r = client.get("/api/rag-eval/overview")
    assert r.status_code == 200
    assert r.json()["present"] is False
    assert r.json()["job"] == "eval-rag"


def test_report_present_and_best_strategy(tmp_path, monkeypatch):
    report = {
        "meta": {"time": "2026-07-15 10:00:00"},
        "retrieval": {
            "A_policy": {
                "vector": {"mrr": 0.4, "recall_at_5": 0.5},
                "hybrid_rerank": {"mrr": 0.9, "recall_at_5": 1.0},
            }
        },
        "evidence_coverage": {},
        "generation": None,
    }
    client = _report(tmp_path, monkeypatch, report)
    r = client.get("/api/rag-eval/overview").json()
    assert r["present"] is True
    assert r["best"] == "hybrid_rerank"
    assert r["generation_done"] is False
    assert r["retrieval"]["A_policy"]["hybrid_rerank"]["mrr"] == 0.9


def test_corrupted_report_treated_as_absent(tmp_path, monkeypatch):
    f = tmp_path / "rag_eval.json"
    f.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(rageval, "_REPORT", f)
    client = TestClient(app)
    assert client.get("/api/rag-eval/overview").json()["present"] is False

