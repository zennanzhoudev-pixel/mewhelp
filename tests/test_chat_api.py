from fastapi.testclient import TestClient

from app.graph import runtime
from app.main import app


def test_chat_stream_includes_actions(monkeypatch):
    async def fake_stream(user_id, message, conversation_id):
        yield {"type": "delta", "text": "抱歉"}
        yield {
            "type": "actions",
            "items": [{"type": "transfer_human"}, {"type": "create_ticket", "draft": {}}],
        }
        yield {"type": "done", "conversation_id": 5}

    monkeypatch.setattr(runtime, "stream_turn", fake_stream)
    client = TestClient(app)
    with client.stream(
        "POST", "/api/chat", json={"user_id": "u1", "message": "我要投诉"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_lines())
    assert '"event": "actions"' in body
    assert "抱歉" in body
    assert "[DONE]" in body


def test_chat_streams_delta_and_done(monkeypatch):
    async def fake_stream(user_id, message, conversation_id):
        yield {"type": "delta", "text": "您好"}
        yield {"type": "done", "conversation_id": 9}

    monkeypatch.setattr(runtime, "stream_turn", fake_stream)
    client = TestClient(app)
    with client.stream(
        "POST", "/api/chat", json={"user_id": "u1", "message": "hi"}
    ) as resp:
        body = "".join(resp.iter_lines())
    assert '"delta": "您好"' in body or '"\\u60a8\\u597d"' in body or "您好" in body
    assert '[DONE]' in body


def test_chat_validates_empty_message(monkeypatch):
    client = TestClient(app)
    assert (
        client.post("/api/chat", json={"user_id": "u1", "message": ""}).status_code == 422
    )


def test_chat_error_frame(monkeypatch):
    async def fake_stream(user_id, message, conversation_id):
        raise runtime.ConversationNotFound(999)
        yield {}

    monkeypatch.setattr(runtime, "stream_turn", fake_stream)
    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/chat",
        json={"user_id": "u1", "message": "hi", "conversation_id": 999},
    ) as resp:
        body = "".join(resp.iter_lines())
    assert "event: error" in body
    assert "[DONE]" not in body

