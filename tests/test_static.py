from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_serves_chat_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    # 页面自包含且对接 /api/chat 的 SSE
    assert "/api/chat" in resp.text
    assert "session_id" in resp.text
    # 后台入口由 auth.js 按角色显隐;viewer 看不到,admin 和本地无鉴权模式可见
    assert 'href="/console"' in resp.text
    assert "data-admin-only" in resp.text


def test_admin_pages_are_reachable():
    """后台各页都能直接开;共享外壳(样式 + 脚本 + 导航)也在静态目录里。"""
    for path, marker in (
        ("/admin", "/api/admin/overview"),
        ("/kb", "/api/kb/overview"),
        ("/rag-eval", "/api/rag-eval/overview"),
        ("/review", "/api/review/queue"),
        ("/observability", "/api/observability/overview"),
        ("/topics", "/api/topics/distribution"),
        ("/topics/questions", "/api/topics/questions"),
        ("/acceptance", "/api/acceptance/overview"),
        ("/acceptance/eval", "/api/acceptance/eval"),
        ("/acceptance/data", "/api/acceptance/data"),
        ("/acceptance/errors", "/api/acceptance/errors"),
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert marker in resp.text, path
        assert "/static/admin.js" in resp.text, path    # 后台导航一份共用
    for asset in ("/static/admin.js", "/static/acceptance.js", "/static/acceptance.css"):
        assert client.get(asset).status_code == 200, asset


def test_identity_and_support_pages_are_reachable():
    for path, marker in (
        ("/login", "扫码登录"),
        ("/qr/approve", "确认登录"),
        ("/console", "/api/admin/overview"),
        ("/agent", "/api/support/workspace/queue"),
        ("/admin/users", "/api/admin/users"),
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert marker in resp.text, path


def test_auth_profile_refresh_preserves_token_and_login_does_not_auto_redirect():
    auth_js = client.get("/static/auth.js").text
    assert "data.token || getToken()" in auth_js
    login_html = client.get("/login").text
    assert "redirectExisting" not in login_html
