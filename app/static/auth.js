/* 共用登录/鉴权:自动给 /api/* 请求加 Bearer token,无 token 时弹登录框。
   引入方式:在所有页面 </body> 前加 <script src="/static/auth.js"></script>。 */
(function () {
  const TOKEN_KEY = "mewhelp_token";
  const rawFetch = window.fetch.bind(window);

  function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function setToken(t) { localStorage.setItem(TOKEN_KEY, t || ""); }
  function clearToken() { localStorage.removeItem(TOKEN_KEY); }

  // 给 /api/*(除 /api/auth/*)加上 Authorization
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const isApi = url.indexOf("/api/") === 0 && url.indexOf("/api/auth/") !== 0;
    let resp;
    if (isApi) {
      const headers = new Headers((init && init.headers) || {});
      const t = getToken();
      if (t) headers.set("Authorization", "Bearer " + t);
      resp = await rawFetch(input, Object.assign({}, init || {}, { headers }));
      if (resp.status === 401) showLogin();
    } else {
      resp = await rawFetch(input, init);
    }
    return resp;
  };

  function injectStyle() {
    if (document.getElementById("mewhelp-auth-style")) return;
    const s = document.createElement("style");
    s.id = "mewhelp-auth-style";
    s.textContent = `
      #mewhelp-auth-mask{position:fixed;inset:0;background:rgba(15,23,42,.55);z-index:99999;display:flex;align-items:center;justify-content:center}
      #mewhelp-auth-box{background:#fff;color:#1f2329;border-radius:14px;padding:26px 28px;width:320px;box-shadow:0 20px 60px rgba(0,0,0,.3);font-family:-apple-system,"PingFang SC",sans-serif}
      #mewhelp-auth-box h3{margin:0 0 6px;font-size:17px}
      #mewhelp-auth-box p{margin:0 0 14px;color:#8a919f;font-size:12px}
      #mewhelp-auth-box input{width:100%;box-sizing:border-box;margin:0 0 10px;padding:9px 11px;border:1px solid #e5e7eb;border-radius:8px;font-size:14px}
      #mewhelp-auth-box button{width:100%;padding:9px 0;border:0;border-radius:8px;background:#4f7cff;color:#fff;font-size:14px;cursor:pointer}
      #mewhelp-auth-err{color:#d54941;font-size:12px;min-height:16px;margin-top:8px}
    `;
    document.head.appendChild(s);
  }

  function showLogin() {
    if (document.getElementById("mewhelp-auth-mask")) return;
    injectStyle();
    const mask = document.createElement("div");
    mask.id = "mewhelp-auth-mask";
    mask.innerHTML = `
      <div id="mewhelp-auth-box">
        <h3>登录 MewHelp</h3>
        <p>请输入账号密码后继续</p>
        <input id="mewhelp-auth-user" placeholder="用户名" autocomplete="username">
        <input id="mewhelp-auth-pass" type="password" placeholder="密码" autocomplete="current-password">
        <button id="mewhelp-auth-submit">登录</button>
        <div id="mewhelp-auth-err"></div>
      </div>`;
    document.body.appendChild(mask);
    const submit = async () => {
      const u = document.getElementById("mewhelp-auth-user").value.trim();
      const p = document.getElementById("mewhelp-auth-pass").value;
      const err = document.getElementById("mewhelp-auth-err");
      err.textContent = "";
      try {
        const r = await rawFetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: u, password: p }),
        });
        const d = await r.json();
        if (!r.ok) { err.textContent = d.detail || "登录失败"; return; }
        setToken(d.token);
        location.reload();
      } catch (e) {
        err.textContent = "网络错误,请重试";
      }
    };
    document.getElementById("mewhelp-auth-submit").addEventListener("click", submit);
    document.getElementById("mewhelp-auth-pass").addEventListener("keydown", (e) => {
      if (e.key === "Enter") submit();
    });
  }

  async function init() {
    try {
      const r = await rawFetch("/api/auth/config");
      const d = await r.json();
      if (!d.auth_enabled) return;          // 未开鉴权:不弹框
      if (!getToken()) { showLogin(); return; }
      const me = await rawFetch("/api/auth/me", {
        headers: { Authorization: "Bearer " + getToken() },
      });
      if (!me.ok) { clearToken(); showLogin(); }
    } catch (e) {
      /* 服务未起时不打扰 */
    }
  }

  window.MewHelpAuth = { getToken, setToken, clearToken, showLogin };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
