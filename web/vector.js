(() => {
  const byId = (id) => document.getElementById(id);

  async function loadEmbeddingStatus() {
    const node = byId("embeddingStatus");
    if (!node) return;
    try {
      const payload = await apiFetch("/api/v1/rag/embeddings/status");
      if (!payload.available) {
        node.textContent = `Vectors unavailable · ${payload.error || "pgvector not ready"}`;
        node.className = "muted vector-status error-text";
        return;
      }
      node.textContent = `Vectors: ${payload.embedded_current_model}/${payload.total_current_chunks} · ${payload.model}`;
      node.className = `muted vector-status${payload.complete ? " complete" : ""}`;
    } catch (error) {
      node.textContent = `Vectors unavailable · ${error.message}`;
      node.className = "muted vector-status error-text";
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

  const form = byId("ragSearchForm");
  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const query = byId("ragSearchQuery").value.trim();
      if (query.length < 2) return;
      const mode = byId("ragSearchMode")?.value || "hybrid";

      setMessage(byId("ragSearchMessage"), `Searching current chunks with ${mode} retrieval…`);
      byId("ragSearchResults").replaceChildren();
      try {
        const payload = await apiFetch(
          `/api/v1/rag/search?q=${encodeURIComponent(query)}&limit=10&mode=${encodeURIComponent(mode)}`,
        );
        const warning = payload.warning ? ` · fallback: ${payload.warning}` : "";
        setMessage(
          byId("ragSearchMessage"),
          `${payload.count} result(s) · ${payload.retrieval}${warning}`,
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
      await window.startEmbeddingBackfill();
      await loadEmbeddingStatus();
    });
  }

  const dashboard = byId("dashboard");
  if (dashboard) {
    const observer = new MutationObserver(() => {
      if (!dashboard.classList.contains("hidden")) loadEmbeddingStatus();
    });
    observer.observe(dashboard, { attributes: true, attributeFilter: ["class"] });
    if (!dashboard.classList.contains("hidden")) loadEmbeddingStatus();
  }

  window.loadEmbeddingStatus = loadEmbeddingStatus;
})();
