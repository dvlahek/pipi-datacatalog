(() => {
  const byId = (id) => document.getElementById(id);

  function authHeaders() {
    const headers = new Headers();
    const token = sessionStorage.getItem("pipiToken");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  }

  function formatDate(value) {
    if (!value) return "—";
    return new Date(value).toLocaleString();
  }

  function durationLabel(run) {
    if (!run.started_at || !run.finished_at) return "—";
    const ms = new Date(run.finished_at) - new Date(run.started_at);
    if (!Number.isFinite(ms) || ms < 0) return "—";
    if (ms < 1000) return `${ms} ms`;
    return `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;
  }

  function kindLabel(kind) {
    if (kind === "provider-sync") return "Provider sync";
    if (kind === "resource-refresh") return "Registered resources";
    return kind || "Harvest";
  }

  function summaryLabel(run) {
    const summary = run.summary || {};
    if (run.run_kind === "provider-sync") {
      return `${summary.discovered ?? 0} discovered · ${summary.inserted ?? 0} new · ${summary.updated ?? 0} changed · ${summary.provider_errors ?? 0} errors`;
    }
    if (run.run_kind === "resource-refresh") {
      return `${summary.checked ?? 0} checked · ${summary.versions_created ?? 0} changed · ${summary.errors ?? 0} errors`;
    }
    return JSON.stringify(summary);
  }

  function statusBadge(status) {
    const badge = document.createElement("span");
    badge.className = "badge";
    if (status === "ok") badge.classList.add("ok");
    if (status === "error") badge.classList.add("error");
    if (status === "partial") badge.classList.add("approval");
    badge.textContent = status || "unknown";
    return badge;
  }

  function cell(text) {
    const td = document.createElement("td");
    td.textContent = text ?? "";
    return td;
  }

  async function loadHarvestRuns() {
    const rows = byId("harvestRows");
    const message = byId("harvestMessage");
    if (!rows || !message) return;

    try {
      const response = await fetch("/api/v1/harvest/runs?limit=10", { headers: authHeaders() });
      if (response.status === 401) return;
      if (!response.ok) throw new Error(`Harvest history request failed (${response.status})`);
      const payload = await response.json();

      rows.replaceChildren();
      message.textContent = payload.count
        ? `Showing ${payload.count} most recent harvest run(s).`
        : "No harvest runs recorded yet.";
      message.className = "message";

      for (const run of payload.data || []) {
        const tr = document.createElement("tr");
        tr.append(cell(formatDate(run.started_at)));
        tr.append(cell(kindLabel(run.run_kind)));
        tr.append(cell(run.trigger || "—"));

        const statusCell = document.createElement("td");
        statusCell.append(statusBadge(run.status));
        tr.append(statusCell);

        const summaryCell = cell(summaryLabel(run));
        if (run.error) {
          const error = document.createElement("span");
          error.className = "sub";
          error.textContent = run.error;
          summaryCell.append(error);
        }
        tr.append(summaryCell);
        tr.append(cell(durationLabel(run)));
        rows.append(tr);
      }
    } catch (error) {
      message.textContent = error.message;
      message.className = "message error";
    }
  }

  const reload = byId("reloadHarvestRuns");
  if (reload) reload.addEventListener("click", () => loadHarvestRuns());

  const dashboard = byId("dashboard");
  if (dashboard) {
    const observer = new MutationObserver(() => {
      if (!dashboard.classList.contains("hidden")) loadHarvestRuns();
    });
    observer.observe(dashboard, { attributes: true, attributeFilter: ["class"] });
    if (!dashboard.classList.contains("hidden")) loadHarvestRuns();
  }

  for (const id of ["datasetMessage", "resourceListMessage"]) {
    const node = byId(id);
    if (!node) continue;
    const observer = new MutationObserver(() => {
      const text = node.textContent || "";
      if (text.includes("Provider sync complete") || text.startsWith("Checked ")) {
        loadHarvestRuns();
      }
    });
    observer.observe(node, { childList: true, subtree: true, characterData: true });
  }

  window.loadHarvestRuns = loadHarvestRuns;
})();
