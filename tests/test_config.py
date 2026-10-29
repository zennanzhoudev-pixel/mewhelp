import pytest
from pydantic import ValidationError

from app.config import Settings


def test_account_scoped_fields_required(monkeypatch):
    # 跟着账号走的必填项,给默认值等于替人猜:猜错不在启动时报错,而是第一次调上游时抛 401
    for k in ("CHAT_MODEL", "CHAT_BASE_URL", "CHAT_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_env_override(monkeypatch):
    for k, v in {
        "CHAT_MODEL": "m",
        "CHAT_BASE_URL": "u",
        "CHAT_API_KEY": "k",
        "EMBED_API_KEY": "e",
        "RERANK_API_KEY": "r",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("TOKEN_BUDGET", "500")
    assert Settings(_env_file=None).token_budget == 500


def test_tuning_constants_have_defaults(monkeypatch):
    for k in ("CHAT_MODEL", "CHAT_BASE_URL", "CHAT_API_KEY", "EMBED_API_KEY", "RERANK_API_KEY"):
        monkeypatch.setenv(k, "x")
    s = Settings(_env_file=None)
    assert s.max_agent_steps == 6
    assert s.rerank_model == "BAAI/bge-reranker-v2-m3"

