def test_create_ticket_action_writes(client, monkeypatch):
    async def fake_create(cid, desc, ttype):
        assert cid == 5 and ttype == "投诉"
        return "T20260715001"

    from app.api import actions
    async def fake_get(cid, tenant_id="default"):
        assert cid == 5 and tenant_id == "default"
        return object()
    monkeypatch.setattr(actions.repository, "get_conversation", fake_get)
    monkeypatch.setattr(actions.repository, "create_ticket", fake_create)
    r = client.post("/api/actions/create-ticket", json={
        "conversation_id": 5, "description": "东西坏了", "ticket_type": "投诉"})
    assert r.status_code == 200
    assert r.json()["ticket_no"] == "T20260715001"


def test_create_ticket_rejects_cross_tenant_conversation(client, monkeypatch):
    from app.api import actions

    async def fake_get(cid, tenant_id="default"):
        return None

    monkeypatch.setattr(actions.repository, "get_conversation", fake_get)
    r = client.post("/api/actions/create-ticket", json={
        "conversation_id": 5, "description": "东西坏了", "ticket_type": "投诉"})
    assert r.status_code == 404


def test_create_ticket_action_rejects_bad_type(client):
    r = client.post("/api/actions/create-ticket", json={
        "conversation_id": 5, "description": "x", "ticket_type": "乱填"})
    assert r.status_code == 422
