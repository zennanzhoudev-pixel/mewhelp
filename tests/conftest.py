import os
import pathlib

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# 测试进程启动即注入占位配置,保证 app.config.Settings() 在无 .env 时也能构造。
# 真实密钥只存在于用户的 .env,绝不写进测试/提交文件。
os.environ.setdefault("CHAT_MODEL", "test-model")
os.environ.setdefault("CHAT_BASE_URL", "http://localhost:9000/v1")
os.environ.setdefault("CHAT_API_KEY", "test-chat-key")
os.environ.setdefault("EMBED_API_KEY", "test-embed-key")
os.environ.setdefault("RERANK_API_KEY", "test-rerank-key")

from app.config import settings  # noqa: E402

_DDL_FILES = [
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch02-ddl.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch03-ddl.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch04-ddl.sql",
]
_TABLES = [
    "faith_cases",
    "low_confidence_questions",
    "messages",
    "tickets",
    "conversations",
    "faq",
    "qa_extraction_staging",
    "knowledge_chunks",
]


def _create_table_stmts() -> list[str]:
    stmts: list[str] = []
    for ddl in _DDL_FILES:
        raw = ddl.read_text(encoding="utf-8")
        sql = "\n".join(
            ln for ln in raw.splitlines() if not ln.lstrip().startswith("--")
        )
        stmts += [
            s.strip()
            for s in sql.split(";")
            if s.strip() and "CREATE TABLE" in s.upper()
        ]
    return stmts


@pytest_asyncio.fixture(scope="session")
async def _test_engine():
    # 本地没有 Docker MySQL 时优雅跳过(CI 里由 mysql:8.0 服务提供,不会跳过)。
    try:
        server_url = settings.test_database_url.rsplit("/", 1)[0]
        admin = create_async_engine(server_url, isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text("DROP DATABASE IF EXISTS mewhelp_test"))
            await conn.execute(text("CREATE DATABASE mewhelp_test CHARACTER SET utf8mb4"))
        await admin.dispose()
    except Exception as exc:  # 连不上 / 凭据不符 / 无建库权限
        pytest.skip(
            f"MySQL 不可用或凭据不符(需 root/root 的测试库):{type(exc).__name__}: {exc}"
        )
    engine = create_async_engine(settings.test_database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            for s in _create_table_stmts():
                await conn.execute(text(s))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"测试库建表失败:{type(exc).__name__}: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session_factory(_test_engine, monkeypatch):
    factory = async_sessionmaker(_test_engine, expire_on_commit=False)
    monkeypatch.setattr("app.db.base.async_session", factory)
    return factory


@pytest_asyncio.fixture()
async def db_clean(_test_engine):
    yield
    async with _test_engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in _TABLES:
            await conn.execute(text(f"TRUNCATE TABLE {t}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

