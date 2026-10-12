(() => {
  const byId = (id) => document.getElementById(id);
  let profiles = [];

  function selectedProfileId() {
    return byId("ragRetrievalProfile")?.value || "";
  }

  function selectedProfile() {
    const profileId = selectedProfileId();
    return profiles.find((item) => item.profile_id === profileId) || null;
  }

  function updateProfileNote() {
    const node = byId("retrievalProfileNote");
    const profile = selectedProfile();
    if (!node || !profile) return;
    const hash = profile.config_hash ? profile.config_hash.slice(0, 12) : "—";
    node.textContent = `${profile.description} · ${profile.profile_id} · config ${hash}`;
  }

  async function loadProfiles() {
    const select = byId("ragRetrievalProfile");
    if (!select) return;
    try {
      const payload = await apiFetch("/api/v1/rag/profiles");
      profiles = payload.data || [];
      const previous = select.value;
      select.replaceChildren();
      for (const profile of profiles) {
        const option = document.createElement("option");
        option.value = profile.profile_id;
        const status = profile.embedding_status;
        const readiness = status
          ? ` · ${status.embedded_current_model}/${status.total_current_chunks}`
          : "";
        option.textContent = `${profile.label}${profile.is_default ? " · default" : ""}${readiness}`;
        select.append(option);
      }
      const fallback = profiles.find((item) => item.is_default)?.profile_id || profiles[0]?.profile_id || "";
      select.value = profiles.some((item) => item.profile_id === previous) ? previous : fallback;
      updateProfileNote();
      await loadEmbeddingStatus();
    } catch (error) {
      select.replaceChildren();
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Retrieval profiles unavailable";
      select.append(option);
      setMessage(byId("ragSearchMessage"), error.message, "error");
    }
  }

  async function loadEmbeddingStatus() {
    const node = byId("embeddingStatus");
    const build = byId("buildEmbeddings");
    if (!node) return;
    const profileId = selectedProfileId();
    if (!profileId) {
      node.textContent = "Vectors: choose a profile";
      if (build) build.disabled = true;
      return;
    }
    try {
      const payload = await apiFetch(`/api/v1/rag/embeddings/status?profile=${encodeURIComponent(profileId)}`);
      if (!payload.available) {
        node.textContent = `Vectors unavailable · ${payload.error || "pgvector not ready"}`;
        node.className = "muted vector-status error-text";
        if (build) build.disabled = true;
        return;
      }
      if (payload.not_applicable) {
        node.textContent = `Vectors: not required · ${profileId}`;
        node.className = "muted vector-status complete";
        if (build) build.disabled = true;
        return;
      }
      node.textContent = `Vectors: ${payload.embedded_current_model}/${payload.total_current_chunks} · ${payload.model}`;
      node.className = `muted vector-status${payload.complete ? " complete" : ""}`;
      if (build) build.disabled = false;
    } catch (error) {
      node.textContent = `Vectors unavailable · ${error.message}`;
      node.className = "muted vector-status error-text";
      if (build) build.disabled = true;
    }
  }

  function renderVectorAwareResults(payload) {
    if (typeof renderRagResults !== "function") return;
    renderRagResults(payload);
    const cards = byId("ragSearchResults")?.querySelectorAll(".rag-result") || [];
    (payload.data || []).forEach((item, index) => {
      const card = cards[index];
      if (!card) return;
      const meta = card.querySelector(".rag-meta");
      if (!meta) return;
      const signals = [];
      if (item.lexical_rank) signals.push(`lexical #${item.lexical_rank}`);
      if (item.vector_rank) signals.push(`vector #${item.vector_rank}`);
      if (item.vector_similarity !== null && item.vector_similarity !== undefined) {
        signals.push(`cos ${Number(item.vector_similarity).toFixed(3)}`);
      }
      if (signals.length) meta.textContent += ` · ${signals.join(" · ")}`;
    });
  }

  const profileSelect = byId("ragRetrievalProfile");
  if (profileSelect) {
    profileSelect.addEventListener("change", async () => {
      updateProfileNote();
      await loadEmbeddingStatus();
    });
  }

  const form = byId("ragSearchForm");
  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const query = byId("ragSearchQuery").value.trim();
      const profileId = selectedProfileId();
      if (query.length < 2 || !profileId) return;

      setMessage(byId("ragSearchMessage"), `Searching with ${profileId}…`);
      byId("ragSearchResults").replaceChildren();
      try {
        const payload = await apiFetch(
          `/api/v1/rag/search?q=${encodeURIComponent(query)}&limit=10&profile=${encodeURIComponent(profileId)}`,
        );
        const warning = payload.warning ? ` · fallback: ${payload.warning}` : "";
        const run = payload.retrieval_run_id ? ` · run #${payload.retrieval_run_id}` : "";
        setMessage(
          byId("ragSearchMessage"),
          `${payload.count} result(s) · ${payload.retrieval}${run}${warning}`,
          payload.count ? "success" : "",
        );
        renderVectorAwareResults(payload);
      } catch (error) {
        setMessage(byId("ragSearchMessage"), error.message, "error");
      }
    }, true);
  }

  const build = byId("buildEmbeddings");
  if (build) {
    build.addEventListener("click", async () => {
      if (!window.startEmbeddingBackfill) {
        setMessage(byId("ragSearchMessage"), "Background job controls are still loading. Try again in a moment.", "error");
        return;
      }
      const profileId = selectedProfileId();
      if (!profileId) return;
      await window.startEmbeddingBackfill(profileId);
      await loadProfiles();
    });
  }

  const dashboard = byId("dashboard");
  if (dashboard) {
    const observer = new MutationObserver(() => {
      if (!dashboard.classList.contains("hidden")) loadProfiles();
    });
    observer.observe(dashboard, { attributes: true, attributeFilter: ["class"] });
    if (!dashboard.classList.contains("hidden")) loadProfiles();
  }

  window.loadEmbeddingStatus = loadEmbeddingStatus;
  window.loadRetrievalProfiles = loadProfiles;
})();
