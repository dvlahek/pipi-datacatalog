(() => {
  const byId = (id) => document.getElementById(id);
  let activeJobId = null;
  let disabledControls = [];

  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function disableDashboardControls() {
    disabledControls = [];
    document.querySelectorAll("#dashboard button, #dashboard input, #dashboard select").forEach((node) => {
      disabledControls.push([node, node.disabled]);
      node.disabled = true;
    });
  }

  function restoreDashboardControls() {
    for (const [node, wasDisabled] of disabledControls) {
      node.disabled = wasDisabled;
    }
    disabledControls = [];
  }

  function showBusy(title, message) {
    document.body.classList.add("portal-locked");
    disableDashboardControls();
    const overlay = byId("busyOverlay");
    byId("busyTitle").textContent = title || "Working…";
    byId("busyMessage").textContent = message || "The operation is running. Please wait.";
    byId("busyDetail").textContent = "Starting background job…";
    const bar = byId("busyProgress");
    bar.classList.add("indeterminate");
    bar.style.width = "35%";
    overlay.classList.remove("hidden");
  }

  function updateBusy(job, elapsedSeconds) {
    const current = job.progress_current;
    const total = job.progress_total;
    const bar = byId("busyProgress");
    if (Number.isFinite(current) && Number.isFinite(total) && total > 0) {
      const percent = Math.max(0, Math.min(100, Math.round((current / total) * 100)));
      bar.classList.remove("indeterminate");
      bar.style.width = `${percent}%`;
    } else {
      bar.classList.add("indeterminate");
      bar.style.width = "35%";
    }

    const stage = job.stage ? String(job.stage).replaceAll("-", " ") : "working";
    const detail = job.message || "Background indexing is running.";
    const progress = Number.isFinite(current) && Number.isFinite(total) && total > 0
      ? ` · ${current}/${total}`
      : "";
    byId("busyDetail").textContent = `${stage}${progress} · ${elapsedSeconds}s · ${detail}`;
  }

  function hideBusy() {
    byId("busyOverlay").classList.add("hidden");
    document.body.classList.remove("portal-locked");
    restoreDashboardControls();
    activeJobId = null;
  }

  function jobSummary(result) {
    const github = result?.github_index;
    if (github) {
      return `${github.files_indexed} repository file(s), ${result.chunk_count} chunk(s), dataset version ${result.dataset_version}.`;
    }
    return `${result?.chunk_count ?? 0} chunk(s), dataset version ${result?.dataset_version ?? "?"}.`;
  }

  async function monitorJob(job, options = {}) {
    if (!job?.id) throw new Error("Background job did not return an ID.");
    activeJobId = job.id;
    const started = Date.now();
    showBusy(options.title || "Indexing…", options.message || "PiPi is indexing the resource in the background.");

    while (true) {
      const currentJob = await apiFetch(`/api/v1/rag/jobs/${activeJobId}`);
      const elapsed = Math.max(0, Math.round((Date.now() - started) / 1000));
      updateBusy(currentJob, elapsed);

      if (currentJob.status === "success") {
        hideBusy();
        const text = `Indexing complete: ${jobSummary(currentJob.result || {})}`;
        if (options.messageNode) setMessage(options.messageNode, text, "success");
        await Promise.all([loadResources(), loadDatasets()]);
        await loadActivityLog();
        return currentJob;
      }

      if (currentJob.status === "error") {
        hideBusy();
        const error = currentJob.error || currentJob.message || "Background indexing failed.";
        if (options.messageNode) setMessage(options.messageNode, error, "error");
        await loadActivityLog();
        throw new Error(error);
      }

      await sleep(750);
    }
  }

  async function startDatasetJob(dataset) {
    const github = dataset.source_system === "github";
    const foi = dataset.source_system === "foi-documents";
    const title = github ? "Indexing GitHub repository" : foi ? "Resolving and indexing document" : "Indexing dataset";
    const message = github
      ? `Reading ${dataset.title}. Large repositories can take a minute or more.`
      : `Indexing ${dataset.title}.`;
    setMessage(byId("datasetMessage"), `${title}: ${dataset.title}…`);

    try {
      const payload = await apiFetch(
        `/api/v1/rag/jobs/datasets/${encodeURIComponent(dataset.identifier)}`,
        { method: "POST" },
      );
      return await monitorJob(payload.job, {
        title,
        message,
        messageNode: byId("datasetMessage"),
      });
    } catch (error) {
      hideBusy();
      setMessage(byId("datasetMessage"), error.message, "error");
      await loadActivityLog();
      return null;
    }
  }

  async function startResourceJob(resource) {
    const github = (resource.detected_type || resource.requested_type) === "github";
    const label = resource.name || resource.source_url;
    const title = github ? "Indexing GitHub repository" : "Indexing resource";
    const message = github
      ? `Reading ${label}. Repository indexing may take a minute or more.`
      : `Indexing ${label}.`;
    setMessage(byId("resourceListMessage"), `${title}: ${label}…`);

    try {
      const payload = await apiFetch(`/api/v1/rag/jobs/resources/${resource.id}`, { method: "POST" });
      return await monitorJob(payload.job, {
        title,
        message,
        messageNode: byId("resourceListMessage"),
      });
    } catch (error) {
      hideBusy();
      setMessage(byId("resourceListMessage"), error.message, "error");
      await loadActivityLog();
      return null;
    }
  }

  function activityBadge(level) {
    const badge = document.createElement("span");
    badge.className = "badge";
    if (level === "error") badge.classList.add("error");
    else if (level === "warning") badge.classList.add("warning");
    else badge.classList.add("ok");
    badge.textContent = level || "info";
    return badge;
  }

  async function loadActivityLog() {
    const rows = byId("activityRows");
    const message = byId("activityMessage");
    if (!rows || !message) return;

    try {
      const payload = await apiFetch("/api/v1/activity?limit=30");
      rows.replaceChildren();
      message.textContent = payload.count
        ? `${payload.count} recent event(s) · ${payload.counts?.error ?? 0} error(s).`
        : "No background activity recorded yet.";
      message.className = `message${payload.counts?.error ? " error" : ""}`;

      for (const item of payload.data || []) {
        const tr = document.createElement("tr");
        if (item.level === "error") tr.classList.add("activity-error-row");
        if (item.level === "warning") tr.classList.add("activity-warning-row");

        const time = document.createElement("td");
        time.textContent = item.created_at ? new Date(item.created_at).toLocaleString() : "—";
        tr.append(time);

        const level = document.createElement("td");
        level.append(activityBadge(item.level));
        tr.append(level);

        for (const value of [item.category, item.action, item.message]) {
          const cell = document.createElement("td");
          cell.textContent = value || "—";
          tr.append(cell);
        }
        rows.append(tr);
      }
    } catch (error) {
      message.textContent = error.message;
      message.className = "message error";
    }
  }

  async function resumeActiveJob() {
    if (activeJobId || byId("dashboard")?.classList.contains("hidden")) return;
    try {
      const payload = await apiFetch("/api/v1/rag/jobs?limit=10");
      const active = (payload.data || []).find((job) => ["queued", "running"].includes(job.status));
      if (!active) return;
      await monitorJob(active, {
        title: "Indexing in progress",
        message: active.label ? `Continuing ${active.label}.` : "A background indexing job is still running.",
        messageNode: byId("resourceListMessage"),
      });
    } catch (error) {
      hideBusy();
      await loadActivityLog();
    }
  }

  // Replace the synchronous portal handlers. Script/API compatibility endpoints remain available.
  window.indexDatasetForRag = startDatasetJob;
  window.indexResourceForRag = startResourceJob;
  window.loadActivityLog = loadActivityLog;

  const reload = byId("reloadActivity");
  if (reload) reload.addEventListener("click", () => loadActivityLog());

  const dashboard = byId("dashboard");
  if (dashboard) {
    const observer = new MutationObserver(() => {
      if (!dashboard.classList.contains("hidden")) {
        loadActivityLog();
        resumeActiveJob();
      }
    });
    observer.observe(dashboard, { attributes: true, attributeFilter: ["class"] });
    if (!dashboard.classList.contains("hidden")) {
      loadActivityLog();
      resumeActiveJob();
    }
  }
})();
