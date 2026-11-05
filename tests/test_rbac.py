"""管理接口 RBAC:无身份 401、viewer 403、admin 放行。"""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.core.deps import require_admin


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_admin)])
    async def protected() -> dict:
        return {"ok": True}

    return app


def test_admin_dependency_fails_closed_without_identity(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    assert TestClient(_app()).get("/protected").status_code == 401


def test_admin_dependency_rejects_viewer(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    app = _app()

    @app.middleware("http")
    async def fake_auth(request, call_next):
        request.state.user = {"sub": "7", "tenant": "t1", "roles": ["viewer"]}
        return await call_next(request)

    assert TestClient(app).get("/protected").status_code == 403


def test_admin_dependency_allows_admin(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    app = _app()

    @app.middleware("http")
    async def fake_auth(request, call_next):
        request.state.user = {"sub": "1", "tenant": "t1", "roles": ["admin"]}
        return await call_next(request)

    resp = TestClient(app).get("/protected")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
