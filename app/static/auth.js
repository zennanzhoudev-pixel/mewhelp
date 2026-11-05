/* MewHelp 统一鉴权外壳:token 注入、未登录跳转、角色路由守卫和账号菜单。
   必须放在 <head>,让页面脚本的第一批 API 请求就带上 Bearer token。 */
(function () {
  const TOKEN_KEY = "mewhelp_token";
  const PROFILE_KEY = "mewhelp_profile";
  const rawFetch = window.fetch.bind(window);
  let identity = null;
  let authEnabled = false;
  const embedded = new URLSearchParams(location.search).get("embed") === "1";
  document.documentElement.dataset.embed = embedded ? "1" : "0";

  function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function getIdentity() {
    if (identity) return identity;
    try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || "null"); }
    catch (_) { return null; }
  }
  function saveSession(data) {
    // /api/auth/me 不返回 token;刷新用户资料时必须保留已有 token,否则会把登录态清空。
    localStorage.setItem(TOKEN_KEY, data.token || getToken());
    const profile = {
      user_id: data.user_id,
      username: data.username,
      display_name: data.display_name || data.username,
      phone: data.phone || "",
      tenant_id: data.tenant_id,
      role: data.role || (data.roles || [])[0] || "customer",
      roles: data.roles || [data.role || "customer"],
    };
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    identity = profile;
    return profile;
  }
  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
    identity = null;
  }
  function role() { return (getIdentity() && getIdentity().role) || ""; }
  function hasRole(...roles) { return roles.includes(role()); }
  function homeFor(r) {
    return r === "admin" ? "/console" : r === "agent" ? "/agent" : "/";
  }
  function loginUrl() {
    const next = location.pathname + location.search;
    return "/login?next=" + encodeURIComponent(next);
  }

  function protectedRoute() {
    if (location.pathname === "/login" || location.pathname === "/qr/approve") return;
    if (!getToken()) location.replace(loginUrl());
  }

  function validateRoute() {
    const p = location.pathname;
    const adminPage = ["/admin", "/kb", "/rag-eval", "/review", "/observability",
      "/topics", "/acceptance", "/console"].some(
      (prefix) => p === prefix || p.startsWith(prefix + "/")
    );
    const agentPage = p === "/agent" || p.startsWith("/agent/");
    if (adminPage && !hasRole("admin")) location.replace(homeFor(role()));
    if (agentPage && !hasRole("agent", "admin")) location.replace(homeFor(role()));
  }

  function updateLegacyAdminLinks() {
    const visible = !authEnabled || hasRole("admin");
    document.querySelectorAll("[data-admin-only]").forEach((el) => { el.hidden = !visible; });
  }

  function injectStyles() {
    if (document.getElementById("mh-account-style")) return;
    const s = document.createElement("style");
    s.id = "mh-account-style";
    s.textContent = `
      #mh-account{position:fixed;right:18px;top:16px;z-index:9998;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
      #mh-account-btn{display:flex;align-items:center;gap:9px;border:1px solid #e5e8ef;background:rgba(255,255,255,.96);border-radius:12px;padding:7px 10px;box-shadow:0 8px 24px rgba(30,45,80,.1);cursor:pointer;color:#202636}
      .mh-avatar{width:28px;height:28px;border-radius:9px;display:grid;place-items:center;color:#fff;background:linear-gradient(135deg,#3370ff,#6b9cff);font-weight:700;font-size:12px}
      #mh-account-name{font-size:13px;font-weight:650;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      #mh-account-menu{display:none;position:absolute;right:0;top:48px;width:220px;background:#fff;border:1px solid #e6e9f0;border-radius:14px;box-shadow:0 20px 55px rgba(20,35,70,.18);overflow:hidden;padding:7px}
      #mh-account-menu.open{display:block}
      .mh-account-head{padding:12px;border-bottom:1px solid #eff1f5;margin-bottom:5px}
      .mh-account-head b{display:block;color:#1f2635;font-size:14px}
      .mh-account-head span{display:block;color:#8b93a5;font-size:11px;margin-top:3px}
      #mh-account-menu a,#mh-account-menu button{display:flex;width:100%;border:0;background:transparent;text-align:left;padding:10px 11px;border-radius:8px;color:#303849;text-decoration:none;font:12px/1.3 inherit;cursor:pointer;box-sizing:border-box}
      #mh-account-menu a:hover,#mh-account-menu button:hover{background:#f3f6ff;color:#245bdb}
      #mh-account-menu .danger{color:#d54941}
      html[data-mh-theme="classic"] #mh-account-btn{border:3px solid #2b2632;border-radius:0;background:#fffaf0;box-shadow:3px 3px 0 #2b2632;font-family:ui-monospace,"SF Mono",Consolas,monospace}
      html[data-mh-theme="classic"] .mh-avatar{border-radius:0;background:#ff7a59;border:2px solid #2b2632}
      html[data-mh-theme="classic"] #mh-account-menu{border:3px solid #2b2632;border-radius:0;box-shadow:5px 5px 0 #2b2632;font-family:ui-monospace,"SF Mono",Consolas,monospace}
      html[data-mh-theme="classic"] #mh-account-menu a,html[data-mh-theme="classic"] #mh-account-menu button{border-radius:0}
      html[data-mh-theme="classic"] #mh-account-menu a:hover,html[data-mh-theme="classic"] #mh-account-menu button:hover{background:#ffedd6;color:#2b2632}
      #mh-pass-mask{display:none;position:fixed;inset:0;background:rgba(22,29,45,.42);z-index:10000;align-items:center;justify-content:center}
      #mh-pass-mask.open{display:flex}
      #mh-pass-box{width:330px;background:#fff;border-radius:16px;padding:22px;box-shadow:0 28px 80px rgba(0,0,0,.25);color:#202636}
      #mh-pass-box h3{margin:0 0 14px;font-size:17px}
      #mh-pass-box label{display:block;font-size:12px;color:#6f788b;margin:10px 0 5px}
      #mh-pass-box input{width:100%;box-sizing:border-box;border:1px solid #dfe3eb;border-radius:9px;padding:9px 10px;font-size:13px}
      .mh-pass-actions{display:flex;gap:9px;justify-content:flex-end;margin-top:16px}
      .mh-pass-actions button{border:0;border-radius:9px;padding:8px 14px;font-size:13px;cursor:pointer}
      .mh-pass-actions .save{background:#3370ff;color:#fff}
      #mh-pass-err{color:#d54941;font-size:12px;min-height:16px;margin-top:8px}
      @media(max-width:640px){#mh-account-name{display:none}#mh-account{right:10px;top:10px}}
    `;
    document.head.appendChild(s);
  }

  function renderAccountMenu() {
    const me = getIdentity();
    if (!me || embedded || document.getElementById("mh-account")) return;
    const modern = ["/console", "/admin/users", "/agent"].includes(location.pathname);
    document.documentElement.dataset.mhTheme = modern ? "modern" : "classic";
    // 顾客聊天页和原有运营后台保持原有视觉；账号菜单只在新的三套工作台显示。
    if (!modern) return;
    injectStyles();
    const box = document.createElement("div");
    box.id = "mh-account";
    const admin = me.role === "admin";
    const agent = me.role === "agent";
    box.innerHTML = `
      <button id="mh-account-btn" type="button">
        <span class="mh-avatar"></span>
        <span id="mh-account-name"></span>
      </button>
      <div id="mh-account-menu">
        <div class="mh-account-head"><b id="mh-menu-name"></b><span id="mh-menu-role"></span></div>
        ${admin ? '<a href="/console">管理控制台</a><a href="/admin/users">账号与权限</a><a href="/agent">人工客服工作台</a>' : ""}
        ${agent ? '<a href="/agent">客服工作台</a>' : ""}
        ${!admin && !agent ? '<a href="/">我的客服</a>' : ""}
        <button type="button" data-action="password">修改密码</button>
        <button type="button" class="danger" data-action="logout">退出登录</button>
      </div>`;
    document.body.appendChild(box);
    const roleLabel = {admin: "管理员", agent: "人工客服", viewer: "只读审核", customer: "顾客"}[me.role] || me.role;
    document.querySelector("#mh-account .mh-avatar").textContent =
      (me.display_name || me.username || "M").slice(0, 1).toUpperCase();
    document.getElementById("mh-account-name").textContent = me.display_name || me.username;
    document.getElementById("mh-menu-name").textContent = me.display_name || me.username;
    document.getElementById("mh-menu-role").textContent = `${roleLabel} · ${me.tenant_id || "default"}`;
    const menu = document.getElementById("mh-account-menu");
    document.getElementById("mh-account-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("open");
    });
    document.addEventListener("click", () => menu.classList.remove("open"));
    menu.addEventListener("click", (e) => e.stopPropagation());
    menu.querySelector("[data-action=logout]").addEventListener("click", () => {
      clearSession();
      location.replace("/login");
    });
    menu.querySelector("[data-action=password]").addEventListener("click", openPasswordDialog);
  }

  function openPasswordDialog() {
    if (document.getElementById("mh-pass-mask")) {
      document.getElementById("mh-pass-mask").classList.add("open");
      return;
    }
    const mask = document.createElement("div");
    mask.id = "mh-pass-mask";
    mask.innerHTML = `
      <div id="mh-pass-box">
        <h3>修改登录密码</h3>
        <label>当前密码</label><input id="mh-old-pass" type="password" autocomplete="current-password">
        <label>新密码（至少 8 位）</label><input id="mh-new-pass" type="password" autocomplete="new-password">
        <label>确认新密码</label><input id="mh-new-pass2" type="password" autocomplete="new-password">
        <div id="mh-pass-err"></div>
        <div class="mh-pass-actions"><button type="button" data-close>取消</button><button type="button" class="save">保存</button></div>
      </div>`;
    document.body.appendChild(mask);
    mask.querySelector("[data-close]").addEventListener("click", () => mask.classList.remove("open"));
    mask.addEventListener("click", (e) => { if (e.target === mask) mask.classList.remove("open"); });
    mask.querySelector(".save").addEventListener("click", async () => {
      const oldPassword = document.getElementById("mh-old-pass").value;
      const next = document.getElementById("mh-new-pass").value;
      const again = document.getElementById("mh-new-pass2").value;
      const err = document.getElementById("mh-pass-err");
      err.textContent = "";
      if (next.length < 8) { err.textContent = "新密码至少 8 位"; return; }
      if (next !== again) { err.textContent = "两次新密码不一致"; return; }
      const resp = await rawFetch("/api/auth/change-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + getToken(),
        },
        body: JSON.stringify({ old_password: oldPassword, new_password: next }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) { err.textContent = data.detail || "修改失败"; return; }
      mask.classList.remove("open");
      alert("密码已修改，请使用新密码重新登录。");
      clearSession();
      location.replace("/login");
    });
  }

  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf("/api/") !== 0) return rawFetch(input, init);
    const headers = new Headers((init && init.headers) || {});
    const token = getToken();
    if (token) headers.set("Authorization", "Bearer " + token);
    const resp = await rawFetch(input, Object.assign({}, init || {}, { headers }));
    if (resp.status === 401 && authEnabled) {
      clearSession();
      location.replace(loginUrl());
    }
    return resp;
  };

  async function init() {
    protectedRoute();
    try {
      const cfgResp = await rawFetch("/api/auth/config");
      const cfg = await cfgResp.json();
      authEnabled = !!cfg.auth_enabled;
      if (!authEnabled) {
        identity = {
          user_id: 0, username: "local-admin", display_name: "本地管理员",
          tenant_id: "default", role: "admin", roles: ["admin"],
        };
        updateLegacyAdminLinks();
        renderAccountMenu();
        window.dispatchEvent(new CustomEvent("mewhelp:auth-ready", { detail: identity }));
        return;
      }
      if (!getToken()) { protectedRoute(); return; }
      const resp = await rawFetch("/api/auth/me", {
        headers: { Authorization: "Bearer " + getToken() },
      });
      if (!resp.ok) {
        clearSession();
        location.replace(loginUrl());
        return;
      }
      saveSession(await resp.json());
      validateRoute();
      updateLegacyAdminLinks();
      renderAccountMenu();
      window.dispatchEvent(new CustomEvent("mewhelp:auth-ready", { detail: identity }));
    } catch (_) {
      /* 服务启动中不打断页面渲染 */
    }
  }

  window.MewHelpAuth = {
    getToken,
    getIdentity,
    getUserId: () => (getIdentity() && String(getIdentity().user_id)) || "",
    saveSession,
    clearSession,
    homeFor,
    hasRole,
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
