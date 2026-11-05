import pytest

from app.config import settings
from app.core import circuit, intent, pii, ratelimit, security, skills


def test_password_hash_roundtrip():
    h = security.hash_password("secret123")
    assert security.verify_password("secret123", h)
    assert not security.verify_password("wrong", h)


def test_token_roundtrip_and_reject(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    token = security.create_token(1, "t1", ["admin"])
    payload = security.decode_token(token)
    assert payload["sub"] == "1"
    assert payload["tenant"] == "t1"
    assert payload["roles"] == ["admin"]
    assert security.decode_token("garbage") is None


def test_pii_mask():
    assert pii.mask_text("手机 13812345678 联系") == "手机 138****5678 联系"
    assert "***" in pii.mask_text("hi@example.com")
    assert pii.mask_value({"k": "13812345678"})["k"] == "138****5678"


def test_rate_limiter(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    rl = ratelimit.RateLimiter(per_minute=0, burst=1)
    assert rl.allow("ip1") is True
    assert rl.allow("ip1") is False


async def test_circuit_opens_and_fast_fails(monkeypatch):
    monkeypatch.setattr(settings, "circuit_breaker_enabled", True)
    cb = circuit.CircuitBreaker("t", threshold=2, recovery=30)

    async def boom():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(boom)
    assert cb.state == "open"
    with pytest.raises(circuit.CircuitOpenError):
        await cb.call(boom)


async def test_intent_cost_fallback(monkeypatch):
    monkeypatch.setattr(settings, "intent_mode", "cost")
    monkeypatch.setattr(settings, "intent_small_model", "small")
    monkeypatch.setattr(settings, "intent_model", "big")
    monkeypatch.setattr(settings, "intent_conf_threshold", 0.6)
    calls = []

    async def fake(q, h, model):
        calls.append(model)
        return {"intent": "物流", "confidence": 0.9 if model == "big" else 0.3}

    monkeypatch.setattr(intent, "_classify_with", fake)
    out = await intent.classify("订单到哪了")
    assert out["intent"] == "物流"
    assert calls == ["small", "big"]


def test_skills_load_and_select(monkeypatch, tmp_path):
    (tmp_path / "refund-policy.md").write_text("# 退款\n以平台规则为准", encoding="utf-8")
    monkeypatch.setattr(settings, "skills_enabled", True)
    monkeypatch.setattr(settings, "skills_dir", str(tmp_path))
    assert "退款" in skills.skill_for_intent("退款退货")
    assert skills.skill_for_intent("闲聊") == ""

