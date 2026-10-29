(function (global) {
  async function api(path, opts) {
    const resp = await fetch(path, opts);
    if (!resp.ok) { const t = await resp.text(); throw new Error(resp.status + " " + t.slice(0, 120)); }
    return resp.json();
  }
  global.ahApi = api;
  global.ahRunJob = async function (name, logEl, onDone) {
    const start = await api("/api/jobs/" + name, { method: "POST" }).catch((e) => { logEl.textContent = e.message; return null; });
    if (!start) return;
    const timer = setInterval(async () => {
      const s = await api("/api/jobs/" + name);
      logEl.textContent = s.tail || "";
      if (s.status !== "running") { clearInterval(timer); if (onDone) onDone(s); }
    }, 1200);
  };
})(window);

