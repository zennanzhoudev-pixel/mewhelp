from fastapi.testclient import TestClient

from app.api import actions
from app.main import app


def test_create_ticket_action_writes(monkeypatch):
    async def fake_create(cid, desc, ttype):
        assert cid == 5 and ttype == "投诉"
        return "T20260715001"

    monkeypatch.setattr(actions.repository, "create_ticket", fake_create)
    client = TestClient(app)
    r = client.post(
        "/api/actions/create-ticket",
        json={"conversation_id": 5, "description": "东西坏了", "ticket_type": "投诉"},
    )
    assert r.status_code == 200
    assert r.json()["ticket_no"] == "T20260715001"


def test_create_ticket_action_rejects_bad_type():
    client = TestClient(app)
    r = client.post(
        "/api/actions/create-ticket",
        json={"conversation_id": 5, "description": "x", "ticket_type": "乱填"},
    )
    assert r.status_code == 422

