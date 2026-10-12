const state = {
  token: sessionStorage.getItem("pipiToken"),
  authEnabled: true,
  datasetsByIdentifier: new Map(),
};

const el = (id) => document.getElementById(id);

function setMessage(node, text, kind = "") {
  node.textContent = text || "";
  node.className = `message${kind ? ` ${kind}` : ""}`;
}

function showLogin(message = "") {
  el("loginPanel").classList.remove("hidden");
  el("dashboard").classList.add("hidden");
  el("logoutButton").classList.add("hidden");
  el("userLabel").textContent = "";
  setMessage(el("loginMessage"), message, message ? "error" : "");
}

function showDashboard(username = "") {
  el("loginPanel").classList.add("hidden");
  el("dashboard").classList.remove("hidden");
  if (state.authEnabled) {
    el("logoutButton").classList.remove("hidden");
    el("userLabel").textContent = username || "Authenticated";
  } else {
    el("logoutButton").classList.add("hidden");
    el("userLabel").textContent = "Local development mode";
  }
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    sessionStorage.removeItem("pipiToken");
    state.token = null;
    showLogin("Session expired or authentication is required.");
    throw new Error("Authentication required");
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = { detail: text }; }
  }
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.error || `Request failed (${response.status})`);
  }
  return payload;
}

function td(text, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = text ?? "";
  return cell;
}

function button(label, onClick, className = "secondary") {
  const node = document.createElement("button");
  node.type = "button";
  node.className = className;
  node.textContent = label;
  node.addEventListener("click", onClick);
  return node;
}

function linkButton(label, url) {
  const node = document.createElement("a");
  node.className = "button-link secondary";
  node.textContent = label;
  node.href = url;
  node.target = "_blank";
  node.rel = "noopener noreferrer";
  return node;
}

function accessLabel(dataset) {
  const distributions = dataset.distributions || [];
  if (!distributions.length) return "—";
  return distributions.map((item) => item.format || item.media_type || item.kind || "access").join(", ");
}

function resourceIsRagIndexable(resource) {
  return ["csv", "json", "document", "text"].includes(resource.detected_type || resource.requested_type);
}

function datasetIsRagIndexable(dataset) {
  if (["sensor-observation", "live-video-stream"].includes(dataset.dataset_type)) return false;
  const distributions = dataset.distributions || [];
  return distributions.some((item) => {
    if (item.kind === "metadata-page") return false;
    const media = String(item.media_type || "").toLowerCase();
    const format = String(item.format || "").toUpperCase();
    return media.startsWith("text/")
      || media === "application/json"
      || media.endsWith("+json")
      || media === "application/pdf"
      || ["CSV", "JSON", "PDF", "TXT", "TEXT", "HTML"].includes(format);
  });
}

async function indexDatasetForRag(dataset) {
  setMessage(el("datasetMessage"), `Indexing ${dataset.title}...`);
  try {
    const payload = await apiFetch(
      `/api/v1/rag/datasets/${encodeURIComponent(dataset.identifier)}/index`,
      { method: "POST" },
    );
    setMessage(
      el("datasetMessage"),
      `Indexed ${dataset.title}: version ${payload.dataset_version}, ${payload.chunk_count} chunk(s).`,
      "success",
    );
  } catch (error) {
    setMessage(el("datasetMessage"), error.message, "error");
  }
}

async function indexResourceForRag(resource) {
  try {
    const payload = await apiFetch(`/api/v1/rag/resources/${resource.id}/index`, { method: "POST" });
    window.alert(`RAG indexing complete: dataset version ${payload.dataset_version}, ${payload.chunk_count} chunk(s).`);
    await Promise.all([loadResources(), loadDatasets()]);
  } catch (error) {
    window.alert(error.message);
  }
}

function appendDatasetActions(dataset, actions) {
  let added = false;
  const distributions = dataset.distributions || [];

  const snapshot = distributions.find((item) => item.kind === "snapshot" || String(item.format || "").toUpperCase() === "JPEG");
  if (snapshot) {
    actions.append(linkButton("Snapshot", snapshot.access_url));
    added = true;
  }

  const liveStream = distributions.find((item) => item.kind === "live-stream" || String(item.format || "").toUpperCase() === "HLS");
  if (liveStream) {
    actions.append(linkButton("Open HLS", liveStream.access_url));
    added = true;
  }

  const metadataPage = distributions.find((item) => item.kind === "metadata-page");
  if (metadataPage) {
    actions.append(linkButton("Open details", metadataPage.access_url));
    added = true;
  }

  if (datasetIsRagIndexable(dataset)) {
    actions.append(button("Index for RAG", () => indexDatasetForRag(dataset)));
    added = true;
  }

  if (!added) {
    const note = document.createElement("span");
    note.className = "muted compact-note";
    note.textContent = dataset.dataset_type === "sensor-observation" ? "Metadata-first" : "Metadata only";
    actions.append(note);
  }
}

async function loadDatasets() {
  const payload = await apiFetch("/api/v1/datasets");
  el("datasetCount").textContent = payload.count;
  const rows = el("datasetRows");
  rows.replaceChildren();
  state.datasetsByIdentifier = new Map();

  for (const dataset of payload.data) {
    state.datasetsByIdentifier.set(dataset.identifier, dataset);

    const row = document.createElement("tr");
    row.append(td(dataset.catalog_id));

    const titleCell = td(dataset.title);
    const identifier = document.createElement("span");
    identifier.className = "sub";
    identifier.textContent = dataset.identifier;
    titleCell.append(identifier);
    row.append(titleCell);

    row.append(td(dataset.dataset_type));
    row.append(td(dataset.source_system));
    row.append(td(accessLabel(dataset)));

    const actionsCell = document.createElement("td");
    const actions = document.createElement("div");
    actions.className = "actions";
    appendDatasetActions(dataset, actions);
    actionsCell.append(actions);
    row.append(actionsCell);

    rows.append(row);
  }
}

async function loadResources() {
  const payload = await apiFetch("/api/v1/resources");
  el("resourceCount").textContent = payload.count;
  const rows = el("resourceRows");
  rows.replaceChildren();

  for (const resource of payload.data) {
    const row = document.createElement("tr");
    row.append(td(String(resource.id)));

    const nameCell = td(resource.name || "Unnamed resource");
    const url = document.createElement("span");
    url.className = "sub";
    url.textContent = resource.source_url;
    nameCell.append(url);
    row.append(nameCell);

    row.append(td(resource.detected_type || resource.requested_type || "auto"));

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${resource.last_error ? "error" : resource.enabled ? "ok" : ""}`;
    badge.textContent = resource.last_error ? "error" : resource.enabled ? "enabled" : "disabled";
    statusCell.append(badge);
    if (resource.last_error) {
      const error = document.createElement("span");
      error.className = "sub";
      error.textContent = resource.last_error;
      statusCell.append(error);
    }
    row.append(statusCell);

    row.append(td(resource.last_checked_at ? new Date(resource.last_checked_at).toLocaleString() : "—"));

    const actionsCell = document.createElement("td");
    const actions = document.createElement("div");
    actions.className = "actions";
    actions.append(button("Refresh", async () => {
      try {
        const payload = await apiFetch(`/api/v1/resources/${resource.id}/refresh`, { method: "POST" });
        const versions = payload.sync?.versions_created || 0;
        setMessage(
          el("resourceListMessage"),
          versions ? `Resource ${resource.id} changed: ${versions} new dataset version(s).` : `Resource ${resource.id} checked: no catalog change.`,
          "success",
        );
        await Promise.all([loadResources(), loadDatasets()]);
      } catch (error) { window.alert(error.message); }
    }));
    if (resource.enabled && resourceIsRagIndexable(resource)) {
      actions.append(button("Index RAG", () => indexResourceForRag(resource)));
    }
    if (resource.enabled) {
      actions.append(button("Disable", async () => {
        try {
          await apiFetch(`/api/v1/resources/${resource.id}`, { method: "DELETE" });
          await loadResources();
        } catch (error) { window.alert(error.message); }
      }));
    } else {
      actions.append(button("Enable", async () => {
        try {
          await apiFetch(`/api/v1/resources/${resource.id}/enable`, { method: "POST" });
          await loadResources();
        } catch (error) { window.alert(error.message); }
      }));
    }
    actionsCell.append(actions);
    row.append(actionsCell);
    rows.append(row);
  }
}

async function loadProviders() {
  const payload = await apiFetch("/api/v1/providers");
  el("providerCount").textContent = payload.count;
}

async function loadDashboard() {
  await Promise.all([loadDatasets(), loadResources(), loadProviders()]);
}

function renderRagResults(payload) {
  const results = el("ragSearchResults");
  results.replaceChildren();

  if (!payload.data.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No indexed chunks matched this query.";
    results.append(empty);
    return;
  }

  for (const item of payload.data) {
    const dataset = state.datasetsByIdentifier.get(item.dataset_identifier);
    const card = document.createElement("article");
    card.className = "result rag-result";

    const heading = document.createElement("div");
    heading.className = "rag-result-head";

    const title = document.createElement("strong");
    title.textContent = dataset?.title || item.dataset_identifier;

    const score = document.createElement("span");
    score.className = "badge";
    score.textContent = `#${item.rank} · score ${item.score}`;
    heading.append(title, score);

    const meta = document.createElement("div");
    meta.className = "rag-meta";
    meta.textContent = `dataset version ${item.dataset_version} · chunk ${item.chunk_index} · ${item.media_type}`;

    const identifier = document.createElement("div");
    identifier.className = "rag-identifier";
    identifier.textContent = item.dataset_identifier;

    const chunk = document.createElement("pre");
    chunk.className = "rag-chunk";
    chunk.textContent = item.text;

    card.append(heading, meta, identifier, chunk);

    if (item.source_url) {
      const source = document.createElement("a");
      source.className = "rag-source";
      source.href = item.source_url;
      source.target = "_blank";
      source.rel = "noopener noreferrer";
      source.textContent = "Open source";
      card.append(source);
    }

    results.append(card);
  }
}

el("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(el("loginMessage"), "Signing in...");
  try {
    const payload = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: el("username").value,
        password: el("password").value,
      }),
    });
    state.token = payload.access_token;
    sessionStorage.setItem("pipiToken", state.token);
    el("password").value = "";
    showDashboard(payload.user?.username || "");
    await loadDashboard();
    setMessage(el("loginMessage"), "");
  } catch (error) {
    showLogin(error.message);
  }
});

el("logoutButton").addEventListener("click", () => {
  state.token = null;
  sessionStorage.removeItem("pipiToken");
  showLogin();
});

el("resourceForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const keywords = el("resourceKeywords").value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  setMessage(el("resourceMessage"), "Validating and ingesting resource...");
  try {
    const payload = await apiFetch("/api/v1/resources", {
      method: "POST",
      body: JSON.stringify({
        source_url: el("resourceUrl").value,
        name: el("resourceName").value || null,
        resource_type: el("resourceType").value,
        publisher: el("resourcePublisher").value || null,
        license: el("resourceLicense").value || null,
        keywords,
      }),
    });

    if (payload.status === "ok") {
      setMessage(el("resourceMessage"), "Resource registered and catalog metadata created.", "success");
      el("resourceForm").reset();
    } else {
      setMessage(el("resourceMessage"), payload.error || "Resource registered, but ingestion failed.", "error");
    }
    await Promise.all([loadResources(), loadDatasets()]);
  } catch (error) {
    setMessage(el("resourceMessage"), error.message, "error");
  }
});

el("searchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = el("searchQuery").value.trim();
  if (!query) return;
  const results = el("searchResults");
  results.replaceChildren();
  try {
    const payload = await apiFetch(`/api/v1/search?q=${encodeURIComponent(query)}`);
    if (!payload.data.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "No matching datasets.";
      results.append(empty);
      return;
    }
    for (const item of payload.data) {
      const card = document.createElement("div");
      card.className = "result";
      const title = document.createElement("strong");
      title.textContent = item.dataset.title;
      const meta = document.createElement("span");
      meta.textContent = `${item.dataset.dataset_type} · ${item.dataset.source_system} · score ${item.score}`;
      card.append(title, meta);
      results.append(card);
    }
  } catch (error) {
    const message = document.createElement("div");
    message.className = "message error";
    message.textContent = error.message;
    results.append(message);
  }
});

el("ragSearchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = el("ragSearchQuery").value.trim();
  if (query.length < 2) return;

  setMessage(el("ragSearchMessage"), "Searching indexed content...");
  el("ragSearchResults").replaceChildren();
  try {
    const payload = await apiFetch(`/api/v1/rag/search?q=${encodeURIComponent(query)}&limit=10`);
    setMessage(
      el("ragSearchMessage"),
      `${payload.count} result(s) · ${payload.retrieval}`,
      payload.count ? "success" : "",
    );
    renderRagResults(payload);
  } catch (error) {
    setMessage(el("ragSearchMessage"), error.message, "error");
  }
});

el("refreshAllResources").addEventListener("click", async () => {
  setMessage(el("resourceListMessage"), "Refreshing enabled registered resources...");
  try {
    const payload = await apiFetch("/api/v1/resources/refresh-enabled", { method: "POST" });
    setMessage(
      el("resourceListMessage"),
      `Checked ${payload.checked}: ${payload.versions_created} new version(s), ${payload.unchanged} unchanged, ${payload.errors} error(s).`,
      payload.errors ? "error" : "success",
    );
    await Promise.all([loadResources(), loadDatasets()]);
  } catch (error) {
    setMessage(el("resourceListMessage"), error.message, "error");
  }
});

el("syncCatalog").addEventListener("click", async () => {
  setMessage(el("datasetMessage"), "Syncing configured providers...");
  try {
    const payload = await apiFetch("/api/v1/catalog/sync", { method: "POST" });
    setMessage(
      el("datasetMessage"),
      `Provider sync complete: ${payload.inserted} inserted, ${payload.updated} updated, ${payload.unchanged} unchanged, ${payload.versions_created} new version(s).`,
      payload.provider_errors ? "error" : "success",
    );
    await Promise.all([loadDatasets(), loadProviders()]);
  } catch (error) {
    setMessage(el("datasetMessage"), error.message, "error");
  }
});

el("reloadResources").addEventListener("click", () => loadResources().catch((error) => window.alert(error.message)));
el("reloadDatasets").addEventListener("click", () => loadDatasets().catch((error) => window.alert(error.message)));

(async function bootstrap() {
  try {
    const auth = await apiFetch("/api/v1/auth/status");
    state.authEnabled = Boolean(auth.enabled);
    if (!state.authEnabled) {
      showDashboard();
      await loadDashboard();
      return;
    }
    if (!state.token) {
      showLogin();
      return;
    }
    showDashboard();
    await loadDashboard();
  } catch (error) {
    if (state.authEnabled) showLogin(error.message);
  }
})();
