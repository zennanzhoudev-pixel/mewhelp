"""独立登录、账号角色与顾客-客服闭环。"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import admin_users, auth, support
from app.config import settings
from app.core import security, sms
from app.core.auth_middleware import AuthMiddleware
from app.db import repository


@pytest.fixture
async def client(db_session_factory):
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(auth.router)
    app.include_router(admin_users.router)
    app.include_router(support.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "sms_debug_return_code", True)


async def test_register_creates_customer_and_password_login(client):
    reg = await client.post("/api/auth/register", json={
        "username": "customer1", "password": "password-123",
        "display_name": "顾客一", "phone": "13800138000", "tenant_id": "t1",
    })
    assert reg.status_code == 200
    assert reg.json()["role"] == "customer"
    assert reg.json()["display_name"] == "顾客一"

    bad = await client.post("/api/auth/login", json={
        "username": "customer1", "password": "wrong-password",
    })
    assert bad.status_code == 401
    ok = await client.post("/api/auth/login", json={
        "username": "customer1", "password": "password-123",
    })
    assert ok.status_code == 200 and ok.json()["user_id"] == reg.json()["user_id"]


async def test_sms_code_is_hashed_and_single_use(client, monkeypatch):
    await repository.create_managed_user(
        "sms-user", security.hash_password("password-123"), "customer", "default",
        phone="13900139000", display_name="短信用户",
    )
    sent = []

    async def fake_send(phone, code):
        sent.append((phone, code))

    monkeypatch.setattr(sms, "send_login_code", fake_send)
    first = await client.post("/api/auth/sms/send", json={"phone": "13900139000"})
    assert first.status_code == 200
    code = first.json()["debug_code"]
    assert sent == [("13900139000", code)]
    row = await repository.latest_login_code("13900139000")
    assert row.code_hash != code

    ok = await client.post("/api/auth/sms/login", json={
        "phone": "13900139000", "code": code,
    })
    assert ok.status_code == 200 and ok.json()["role"] == "customer"
    reused = await client.post("/api/auth/sms/login", json={
        "phone": "13900139000", "code": code,
    })
    assert reused.status_code == 401


async def test_qr_login_requires_mobile_approval_and_is_one_time(client):
    start = await client.post("/api/auth/qr/start")
    assert start.status_code == 200
    data = start.json()
    assert (await client.get(data["qr_svg"])).headers["content-type"].startswith("image/svg+xml")
    assert (await client.get(f"/api/auth/qr/{data['ticket']}/status")).json()["status"] == "pending"

    reg = await client.post("/api/auth/register", json={
        "username": "qr-user", "password": "password-123", "tenant_id": "default",
    })
    token = reg.json()["token"]
    approved = await client.post(
        f"/api/auth/qr/{data['ticket']}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approved.status_code == 200
    claimed = await client.get(f"/api/auth/qr/{data['ticket']}/status")
    assert claimed.status_code == 200 and claimed.json()["token"]
    assert (await client.get(f"/api/auth/qr/{data['ticket']}/status")).json()["status"] == "consumed"


async def test_admin_user_management_enforces_admin_role(client):
    admin = await repository.create_managed_user(
        "admin1", security.hash_password("password-123"), "admin", "default",
        phone=None, display_name="管理员",
    )
    viewer = await repository.create_managed_user(
        "viewer1", security.hash_password("password-123"), "viewer", "default",
        phone=None, display_name="审核员",
    )
    admin_token = security.create_token(admin, "default", ["admin"])
    viewer_token = security.create_token(viewer, "default", ["viewer"])

    assert (await client.get(
        "/api/admin/users", headers={"Authorization": f"Bearer {viewer_token}"}
    )).status_code == 403
    created = await client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "agent1", "password": "password-123",
            "display_name": "客服一", "role": "agent",
        },
    )
    assert created.status_code == 200 and created.json()["role"] == "agent"


async def test_customer_transfer_agent_claim_reply_and_close(client):
    customer = await repository.create_managed_user(
        "customer2", security.hash_password("password-123"), "customer", "default",
        phone=None, display_name="顾客二",
    )
    agent = await repository.create_managed_user(
        "agent2", security.hash_password("password-123"), "agent", "default",
        phone=None, display_name="客服二",
    )
    cid = await repository.create_conversation(str(customer), "default")
    await repository.append_message(cid, "user", "我要转人工", sender_type="user")
    customer_token = security.create_token(customer, "default", ["customer"])
    agent_token = security.create_token(agent, "default", ["agent"])
    ch = {"Authorization": f"Bearer {customer_token}"}
    ah = {"Authorization": f"Bearer {agent_token}"}

    transferred = await client.post(
        "/api/support/request", headers=ch,
        json={"conversation_id": cid, "reason": "需要人工处理"},
    )
    assert transferred.status_code == 200 and transferred.json()["status"] == "已转人工"
    queue = await client.get("/api/support/workspace/queue", headers=ah)
    assert queue.status_code == 200 and queue.json()["waiting"] == 1
    assert (await client.post(
        f"/api/support/workspace/{cid}/claim", headers=ah
    )).status_code == 200
    replied = await client.post(
        f"/api/support/workspace/{cid}/reply", headers=ah,
        json={"content": "您好，我来协助处理。"},
    )
    assert replied.status_code == 200
    messages = await client.get(
        f"/api/support/{cid}/messages",
        headers=ch,
        params={"after_id": 0},
    )
    assert messages.status_code == 200
    assert any(m["sender_type"] == "agent" and "协助处理" in m["content"]
               for m in messages.json()["items"])
    closed = await client.post(f"/api/support/workspace/{cid}/close", headers=ah)
    assert closed.status_code == 200
    status = await client.get(f"/api/support/{cid}/status", headers=ch)
    assert status.json()["status"] == "已结束"


async def test_customer_cannot_access_another_customer_conversation(client):
    owner = await repository.create_managed_user(
        "owner", security.hash_password("password-123"), "customer", "default",
        phone=None, display_name="会话所有者",
    )
    other = await repository.create_managed_user(
        "other", security.hash_password("password-123"), "customer", "default",
        phone=None, display_name="其他顾客",
    )
    cid = await repository.create_conversation(str(owner), "default")
    token = security.create_token(other, "default", ["customer"])
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get(
        f"/api/support/{cid}/status", headers=headers
    )).status_code == 404
    assert (await client.post(
        "/api/support/request", headers=headers,
        json={"conversation_id": cid, "reason": "越权测试"},
    )).status_code == 404
