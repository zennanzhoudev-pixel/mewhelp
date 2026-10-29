from fastapi.testclient import TestClient

from app.graph import runtime
from app.main import app


def test_agent_endpoint_returns_tool_trace(monkeypatch):
    state = {
        "answer": "订单 1001 正在运输中。",
        "messages": [],
        "suggested_actions": [],
    }

    async def fake_run(user_id, message, conversation_id):
        return {"conversation_id": 12, "state": state}

    monkeypatch.setattr(runtime, "run_turn", fake_run)
    client = TestClient(app)
    r = client.post("/api/agent", json={"user_id": "u1", "message": "订单 1001 到哪了"})
    assert r.status_code == 200
    assert r.json()["conversation_id"] == 12
    assert r.json()["answer"] == "订单 1001 正在运输中。"


def test_agent_endpoint_404_on_unknown_conversation(monkeypatch):
    async def fake_run(*a, **k):
        raise runtime.ConversationNotFound(999)

    monkeypatch.setattr(runtime, "run_turn", fake_run)
    client = TestClient(app)
    r = client.post(
        "/api/agent", json={"user_id": "u1", "message": "hi", "conversation_id": 999}
    )
    assert r.status_code == 404


def test_agent_endpoint_422_on_missing_fields():
    client = TestClient(app)
    assert client.post("/api/agent", json={"message": "hi"}).status_code == 422

