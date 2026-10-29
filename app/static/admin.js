(function (global) {
  const style = `
    .admin-nav { display:flex; gap:8px; flex-wrap:wrap; padding:10px 18px; background:#fff; border-bottom:1px solid #e5e7eb; }
    .admin-nav a { color:#4f7cff; text-decoration:none; font-size:13px; padding:5px 12px; border-radius:8px; }
    .admin-nav a.active { background:#eaf1ff; }
    .admin-card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:14px 16px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
    .admin-card h3 { margin:0 0 6px; font-size:15px; }
    .pill { display:inline-block; font-size:12px; border-radius:999px; padding:2px 9px; }
    .pill.ok { background:#e7f8ef; color:#178a50; }
    .pill.warn { background:#fff5e5; color:#b26a00; }
    .pill.off { background:#f3f4f6; color:#8a919f; }
    .pill.err { background:#fdeceb; color:#c0392b; }
    .admin-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:14px; padding:18px; }
    .kpi { font-size:22px; font-weight:600; }
  `;
  function injectCss() {
    if (document.getElementById("admin-common-css")) return;
    const el = document.createElement("style"); el.id = "admin-common-css"; el.textContent = style; document.head.appendChild(el);
  }
  function mountAdminNav(active) {
    injectCss();
    const nav = document.createElement("nav"); nav.className = "admin-nav";
    const links = [
      ["/admin", "总览"],
      ["/kb", "知识库"],
      ["/rag-eval", "RAG 评估"],
      ["/", "聊天页"],
    ];
    for (const [href, label] of links) {
      const a = document.createElement("a"); a.href = href; a.textContent = label;
      if (href === active) a.className = "active";
      nav.appendChild(a);
    }
    document.body.prepend(nav);
  }
  global.mountAdminNav = mountAdminNav;
  global.adminCssInjected = injectCss;
})(window);

