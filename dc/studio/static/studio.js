(() => {
  "use strict";

  const app = document.getElementById("studio-app");
  if (!app) return;

  const token = app.dataset.token || "";
  const lan = app.dataset.lan === "true";
  const headers = {"Content-Type": "application/json", "X-DC-Token": token};
  const state = {
    jobs: [], candidates: [], exports: [], view: "home", selectedId: null, selectedJobId: null,
    editing: false, pendingJobId: null, pollingJobId: null, progress: null,
    lastExport: null, showTests: false, activities: [], connected: true,
    controls: {}, speakerHints: true, homeForm: null, activeJob: null, cancelConfirm: false, reviewGroupId: null,
    reviewPending: {}, reviewFeedback: {}, reviewExports: [], exportFocusId: null,
    editGroup: "speaker", editAdvanced: false, editSession: null, editSavePending: false, editDiscardConfirm: false, savedHeadlineReadback: null,
  };
  const activeJobKey = "debate-clipper-active-job";
  const findStages = [
    {key: "ingest", label: "Checking your video"},
    {key: "transcribe", label: "Listening to the debate"},
    {key: "select", label: "Finding the best moments"},
    {key: "review", label: "Preparing your clips"},
  ];
  const formatElapsed = milliseconds => {
    const seconds = Math.max(0, Math.floor((Number(milliseconds) || 0) / 1000));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  };
  const readActiveJob = () => {
    try {
      const value = JSON.parse(localStorage.getItem(activeJobKey) || "null");
      return value && value.jobId && Number.isFinite(Number(value.startedAt)) ? value : null;
    } catch { return null; }
  };
  const saveActiveJob = () => {
    if (!state.activeJob) return;
    try { localStorage.setItem(activeJobKey, JSON.stringify(state.activeJob)); } catch {}
  };
  const clearActiveJob = () => {
    state.activeJob = null;
    try { localStorage.removeItem(activeJobKey); } catch {}
  };
  const stageIndex = progress => {
    const index = Number(progress?.stage_index);
    if (Number.isInteger(index)) return Math.max(0, Math.min(findStages.length, index));
    const found = findStages.findIndex(item => item.key === progress?.stage);
    return found < 0 ? 0 : found + 1;
  };
  const stageLabel = progress => progress?.label || (progress?.stage === "queued" ? "Starting" : findStages[Math.max(0, stageIndex(progress) - 1)]?.label) || "Working";
  const rememberStage = progress => {
    if (!state.activeJob) return;
    const measuredJobStart = Date.parse(progress?.started_at || "");
    if (Number.isFinite(measuredJobStart) && state.activeJob.startedAt !== measuredJobStart) {
      state.activeJob.startedAt = measuredJobStart;
      saveActiveJob();
    }
    const stage = progress?.stage || findStages[stageIndex(progress)]?.key || "queued";
    const measuredStart = Date.parse(progress?.stage_started_at || "");
    const stageStartedAt = Number.isFinite(measuredStart) ? measuredStart : Date.now();
    if (state.activeJob.stage !== stage) {
      state.activeJob.stage = stage;
      state.activeJob.stageStartedAt = stageStartedAt;
      saveActiveJob();
    } else if (Number.isFinite(measuredStart) && state.activeJob.stageStartedAt !== measuredStart) {
      state.activeJob.stageStartedAt = measuredStart;
      saveActiveJob();
    }
  };
  state.activeJob = readActiveJob();

  const node = (parent, tag, text, className = "") => {
    const result = document.createElement(tag);
    if (text !== undefined) result.textContent = String(text);
    if (className) result.className = className;
    parent.appendChild(result);
    return result;
  };
  const button = (parent, text, handler, className = "") => {
    const result = node(parent, "button", text, className);
    result.type = "button";
    result.addEventListener("click", () => handler(result));
    return result;
  };
  const input = (parent, type, value = "", placeholder = "") => {
    const result = node(parent, "input");
    result.type = type;
    result.value = value ?? "";
    result.placeholder = placeholder;
    return result;
  };
  const select = (parent, values, current, labels = {}) => {
    const result = node(parent, "select", undefined, "field-select");
    values.forEach(value => {
      const option = node(result, "option", labels[value] || value);
      option.value = value;
    });
    result.value = current || values[0];
    return result;
  };
  const clear = element => element.replaceChildren();
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const fmtTime = seconds => {
    const value = Math.max(0, Number(seconds) || 0);
    return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
  };
  const fmtSize = bytes => {
    const value = Number(bytes) || 0;
    return value > 1048576 ? `${(value / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB`;
  };
  const fmtDate = value => value ? new Date(value).toLocaleString() : "Unknown date";
  const measured = value => typeof value === "number" && Number.isFinite(value);
  const withToken = value => lan && value && !String(value).includes("token=") ? `${value}${String(value).includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}` : value;
  const youtubeVideoId = value => {
    try {
      const url = new URL(value);
      const host = url.hostname.toLowerCase().replace(/^www\./, "");
      let candidate = "";
      if (host === "youtu.be") candidate = url.pathname.split("/").filter(Boolean)[0] || "";
      else if (["youtube.com", "m.youtube.com", "music.youtube.com"].includes(host)) {
        candidate = url.searchParams.get("v") || "";
        if (!candidate) {
          const parts = url.pathname.split("/").filter(Boolean);
          if (parts.length >= 2 && ["shorts", "embed", "live"].includes(parts[0])) candidate = parts[1];
        }
      } else return "";
      return /^[A-Za-z0-9_-]{11}$/.test(candidate) ? candidate : "";
    } catch { return ""; }
  };
  const scoreWord = score => !measured(score) ? "Not measured" : Number(score) >= 90 ? "Great" : Number(score) >= 80 ? "Good" : Number(score) >= 70 ? "Okay" : "Weak";
  const scoreClass = score => !measured(score) ? "rating-unmeasured" : Number(score) >= 90 ? "rating-great" : Number(score) >= 80 ? "rating-good" : Number(score) >= 70 ? "rating-okay" : "rating-weak";
  const titleFor = record => record.decision && Object.prototype.hasOwnProperty.call(record.decision, "headline") ? record.decision.headline : record.hook?.headline_options?.[0] || record.text?.split(/\s+/).slice(0, 8).join(" ") || "A possible moment";
  // FIX3 (Pax, 2026-10-11): the banner inside the preview video is baked
  // in with the AUTO headline. When the current/saved headline differs
  // from the auto one, cover the banner's headline zone with a live
  // overlay showing the headline that will actually be exported.
  // Chrome geometry (dc/chrome.py + job layout regions, 1080x1920
  // canvas): hook zone x=140, w=800; banner bottom = feed y=509.
  const HOOK_ZONE = {left: (140 / 1080) * 100, width: (800 / 1080) * 100, top: (308 / 1920) * 100, height: ((509 - 308) / 1920) * 100};
  const applyHeadlineOverlay = (shell, record, overrideText) => {
    if (!shell || !record) return;
    shell.querySelector(".headline-overlay")?.remove();
    const current = overrideText !== undefined ? overrideText : currentHeadlineFor(record);
    const auto = record.hook?.headline_options?.[0] || "";
    if (!current || current === auto) return;
    const layer = node(shell, "div", undefined, "headline-overlay");
    layer.style.left = `${HOOK_ZONE.left}%`;
    layer.style.width = `${HOOK_ZONE.width}%`;
    layer.style.top = `${HOOK_ZONE.top}%`;
    layer.style.height = `${HOOK_ZONE.height}%`;
    const text = node(layer, "span", current, "headline-overlay-text");
    post("/api/fit", {headline: current}).then(result => {
      const scale = shell.clientWidth / 1080;
      text.style.fontSize = `${Math.max(9, Math.round((result.font_px || 44) * scale))}px`;
    }).catch(() => {});
  };
  const stateFor = record => record.export ? "Exported" : record.uiState || (record.decision?.action === "approve" ? "Approved" : record.decision?.action === "reject" ? "Rejected" : "Not reviewed");
  const stateClass = value => String(value).toLowerCase().replaceAll(" ", "-");
  const sourceGroupFor = record => record.source_group_id || record.source?.source_group_id || record.source_id || `job:${record.job_id}`;
  const sourceTitleFor = record => record.source?.title || "Debate video";
  const runFor = record => record.run_id || record.source?.run_id || record.job_id;
  const reviewActionFor = record => record.uiState || record.decision?.action || "";
  const rightsHelp = {
    unknown: "Not sure: you can review locally, but publishing stays blocked.",
    own: "I made or own this video.",
    permission: "I have permission from the rights holder.",
    licensed: "I have a licence covering this use.",
    public_domain_verified: "I checked that this is public domain.",
  };
  const scoreNames = {
    narrative: "Complete story", conflict: "Disagreement", hook: "Strong opening", clarity: "Easy to follow",
    rebuttal: "Response included", ending: "Clean ending", context: "Enough context",
  };

  try { state.activities = JSON.parse(localStorage.getItem("debate-clipper-activity") || "[]").slice(0, 20); } catch {}
  try { state.speakerHints = localStorage.getItem("speaker-frame-hints") !== "off"; } catch {}
  try { state.editAdvanced = localStorage.getItem("debate-clipper-edit-mode") === "advanced"; } catch {}

  const videos = window.DebateClipperVideoRegistry || {
    register(video) { return video; },
    stopAll() {},
  };

  const setConnection = connected => {
    state.connected = connected;
    const bar = document.getElementById("connection-bar");
    if (bar) bar.hidden = connected;
  };
  const addActivity = (text, result = "success") => {
    state.activities.unshift({time: new Date().toISOString(), text, result});
    state.activities = state.activities.slice(0, 20);
    try { localStorage.setItem("debate-clipper-activity", JSON.stringify(state.activities)); } catch {}
  };
  const showMessage = (kind, title, detail = "", extras = {}) => {
    const box = document.getElementById("app-message");
    clear(box);
    box.className = `message message-${kind}`;
    const row = node(box, "div", undefined, "message-row");
    node(row, "strong", title);
    button(row, "Close", () => { box.className = "sr-only"; }, "message-close");
    if (detail) node(box, "p", detail, "message-detail");
    if (extras.progress) box.appendChild(extras.progress);
    if (extras.actions) {
      const actions = node(box, "div", undefined, "message-actions");
      extras.actions.forEach(action => button(actions, action.label, action.handler, "button-secondary"));
    }
    if (extras.details) {
      const detailButton = button(box, "Show details", async () => {
        detailButton.disabled = true;
        try { node(box, "pre", (await get(`/api/jobs/${encodeURIComponent(extras.details)}/log`)).log, "error-details"); }
        catch (error) { node(box, "pre", error.message, "error-details"); }
      }, "details-button");
    }
  };
  const post = async (path, payload) => {
    const response = await fetch(path, {method: "POST", headers, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) {
      const error = Error(data.detail || "The action could not be completed.");
      error.status = response.status; error.attempt = data.attempt;
      throw error;
    }
    setConnection(true);
    return data;
  };
  const get = async path => {
    const response = await fetch(withToken(path));
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || "The information could not be loaded.");
    setConnection(true);
    return data;
  };
  const getFreshCandidate = async record => {
    const path = `/api/candidates/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}?fresh=${Date.now()}`;
    const response = await fetch(withToken(path), {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || "The saved clip could not be loaded from the server.");
    setConnection(true);
    return data;
  };
  const savedHeadlineText = headline => headline ? `Saved headline: "${headline}"` : "Saved headline: (empty)";
  const applyFreshCandidate = (record, fresh) => {
    if (!fresh) return;
    const current = state.candidates.find(item => reviewKey(item) === reviewKey(record)) || record;
    [record, current].forEach(item => { Object.assign(item, fresh); });
  };
  const actionButton = async (element, busyText, work) => {
    if (element.disabled) return;
    const old = element.textContent;
    element.disabled = true;
    element.classList.add("is-busy");
    element.textContent = busyText;
    try { return await work(); }
    finally { element.disabled = false; element.classList.remove("is-busy"); element.textContent = old; }
  };

  const refresh = async () => {
    const data = await get("/api/jobs");
    state.jobs = data.jobs || [];
    state.candidates = data.candidates || [];
    if (Array.isArray(data.review_exports)) {
      const serverAttempts = data.review_exports;
      const serverIds = new Set(serverAttempts.map(item => item.export_id));
      state.reviewExports = [...serverAttempts, ...state.reviewExports.filter(item => !serverIds.has(item.export_id))];
    }
    const exportsData = await get("/api/exports");
    state.exports = exportsData.exports || [];
    return data;
  };
  const refreshSystem = async () => {
    try {
      const data = await get("/api/system");
      const cpu = data.cpu_percent === null ? "Not measured" : `${Math.round(data.cpu_percent)}%`;
      const ram = data.ram_percent === null ? "Not measured" : `${Math.round(data.ram_percent)}%`;
      const header = document.getElementById("system");
      if (header) header.textContent = `Computer ready · CPU ${cpu} · RAM ${ram}`;
    } catch {}
  };
  const toBase64 = async file => {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
    return btoa(binary);
  };
  const stopVideos = () => { try { videos.stopAll(true); } catch {} };

  const showView = view => {
    state.view = view;
    ["home", "find", "review", "export", "exports"].forEach(name => {
      const section = document.getElementById(`${name}-view`);
      if (section) section.classList.toggle("active-view", name === view);
    });
    const activeStep = view === "home" ? "home" : view === "find" ? "find" : view === "review" ? "review" : "export";
    document.querySelectorAll(".step").forEach(step => step.classList.toggle("active", step.dataset.view === activeStep));
    document.querySelectorAll(".step").forEach(step => {
      const order = ["home", "find", "review", "export"].indexOf(step.dataset.view);
      const current = ["home", "find", "review", "export"].indexOf(activeStep);
      step.classList.toggle("done", order >= 0 && order < current);
    });
  };
  const addHint = (parent, key, text) => {
    let dismissed = false;
    try { dismissed = localStorage.getItem(`debate-clipper-hint-${key}`) === "off"; } catch {}
    if (dismissed) return;
    const hint = node(parent, "div", undefined, "hint");
    node(hint, "span", text);
    button(hint, "Got it", () => { try { localStorage.setItem(`debate-clipper-hint-${key}`, "off"); } catch {} hint.remove(); });
  };
  const renderActivity = parent => {
    if (!state.activities.length) return;
    const section = node(parent, "section", undefined, "activity");
    const heading = node(section, "div", undefined, "section-title");
    node(heading, "h2", "Recent actions");
    node(heading, "span", "Only on this computer", "help");
    state.activities.forEach(item => node(section, "p", `${new Date(item.time).toLocaleString()} · ${item.text}`));
  };

  const renderRecent = parent => {
    let recent = parent.querySelector(".recent");
    if (!recent) recent = node(parent, "section", undefined, "recent");
    clear(recent);
    const title = node(recent, "div", undefined, "section-title");
    node(title, "h2", "Recent videos");
    const visibleJobs = state.jobs.filter(job => !job.is_test).slice(0, 8);
    if (!visibleJobs.length) node(recent, "p", "No videos are ready yet. Add one above to get started.", "empty");
    visibleJobs.forEach(job => {
      const row = node(recent, "div", undefined, "job-row");
      const info = node(row, "div");
      node(info, "strong", job.title || "Video");
      const duration = job.duration ? ` · ${fmtTime(job.duration)}` : "";
      node(info, "span", `${job.progress?.label || "Working"}${duration}`);
      const bar = node(row, "div", undefined, "job-progress");
      const fill = node(bar, "span");
      if (job.progress?.percent !== null && job.progress?.percent !== undefined) fill.style.width = `${job.progress.percent}%`;
      else fill.classList.add("indeterminate");
      if (["awaiting_review", "needs_review"].includes(job.state)) button(row, "Review clips", () => { state.selectedId = null; state.selectedJobId = null; state.candidates = state.candidates.filter(record => record.job_id === job.job_id); renderReview(state.candidates); }, "button-secondary");
      if (["queued", "running", "rendering"].includes(job.state)) button(row, "View progress", async () => {
        state.activeJob = state.activeJob || {jobId: job.job_id, title: job.title, startedAt: Date.now(), stage: job.progress?.stage || "queued", stageStartedAt: Date.now()};
        state.pendingJobId = job.job_id;
        saveActiveJob();
        await refreshActiveJob();
      }, "button-secondary");
      if (job.state === "failed") button(row, "View problem", async () => { showMessage("error", "This video has a problem", "Open the details to see what happened.", {details: job.job_id}); }, "button-secondary");
    });
  };

  const renderHome = () => {
    stopVideos();
    const view = document.getElementById("home-view");
    clear(view);
    addHint(view, "home", "You can leave every option alone. Paste a link and press Find clips.");
    const hero = node(view, "div", undefined, "hero");
    node(hero, "p", "Debate Clipper", "eyebrow");
    node(hero, "h1", "Turn a long debate into clear short clips.");
    node(hero, "p", "Add a video, let Debate Clipper find the moments, then choose what to keep.");
    const add = node(view, "section", undefined, "add-box narrow");
    node(add, "h2", "Add a debate video");
    node(add, "p", "Paste a YouTube link or drop a video file here.", "big-help");
    const active = state.activeJob && state.pendingJobId;
    if (active) {
      const notice = node(add, "div", undefined, "active-job-notice");
      node(notice, "strong", "A video is already being processed");
      node(notice, "span", `${state.activeJob.title || "Video"} · ${stageLabel(state.progress || {stage: state.activeJob.stage})}`);
      button(notice, "View progress", async () => { await refreshActiveJob(); }, "button-secondary");
    }
    const url = input(add, "url", "", "Paste a YouTube link here");
    url.className = "source-input";
    const fileLabel = node(add, "label", "Or drop a video file here", "drop-zone");
    const file = input(fileLabel, "file");
    file.accept = "video/*";
    const fileStatus = node(add, "p", "A link will be used if you paste one.", "file-status");
    const removeFile = button(add, "Remove file", () => {
      file.value = "";
      fileLabel.classList.remove("has-file");
      delete fileLabel.dataset.fileName;
      removeFile.hidden = true;
      syncForm();
    }, "link-button");
    removeFile.hidden = true;
    const options = node(add, "details", undefined, "more-options");
    node(options, "summary", "More options");
    const fields = node(options, "div", undefined, "option-fields");
    const rightsLabel = node(fields, "label", "Rights for this video");
    const rights = select(rightsLabel, ["unknown", "own", "permission", "licensed", "public_domain_verified"], "unknown", {unknown: "I’m not sure", own: "It is mine", permission: "I have permission", licensed: "I have a licence", public_domain_verified: "Verified public domain"});
    const rightsNote = node(rightsLabel, "span", rightsHelp.unknown, "help");
    rights.addEventListener("change", () => { rightsNote.textContent = rightsHelp[rights.value] || rightsHelp.unknown; });
    const countLabel = node(fields, "label", "How many clips should we find?");
    const count = select(countLabel, ["5", "8", "12"], "8", {5: "5 clips", 8: "8 clips", 12: "12 clips"});
    if (state.homeForm) {
      url.value = state.homeForm.url;
      count.value = state.homeForm.count;
      rights.value = state.homeForm.rights;
      rightsNote.textContent = rightsHelp[rights.value] || rightsHelp.unknown;
      if (state.homeForm.file) {
        try { const transfer = new DataTransfer(); transfer.items.add(state.homeForm.file); file.files = transfer.files; } catch {}
        fileLabel.classList.add("has-file");
        fileLabel.dataset.fileName = state.homeForm.file.name;
        fileStatus.textContent = `${state.homeForm.file.name} · ${fmtSize(state.homeForm.file.size)}. A link will take priority if you enter one.`;
        removeFile.hidden = false;
      }
    }
    const syncForm = () => {
      state.homeForm = {url: url.value, count: count.value, rights: rights.value, file: file.files?.[0] || null};
      fileStatus.textContent = url.value.trim() ? "Link will be used." : file.files?.[0] ? `${file.files[0].name} · ${fmtSize(file.files[0].size)}.` : "A link will be used if you paste one.";
    };
    const setSourceLocked = locked => {
      url.disabled = locked;
      file.disabled = locked;
      rights.disabled = locked;
      count.disabled = locked;
      removeFile.disabled = locked;
      fileLabel.classList.toggle("is-locked", locked);
    };
    url.addEventListener("input", syncForm);
    count.addEventListener("change", syncForm);
    rights.addEventListener("change", syncForm);
    const start = button(add, "Find clips", async element => actionButton(element, file.files?.[0] && !url.value.trim() ? "Copying…" : "Starting…", async () => {
      if (state.activeJob && state.pendingJobId) { await refreshActiveJob(); return; }
      syncForm();
      if (url.value.trim() && !youtubeVideoId(url.value.trim())) {
        showMessage("error", "That link does not look like a YouTube video", "Check the link and try again. Your link was kept.");
        return;
      }
      if (!url.value.trim() && !file.files?.[0]) { showMessage("error", "Add a video first", "Paste a link or choose a video file, then try again."); return; }
      setSourceLocked(true);
      try {
        const payload = {rights_class: rights.value, rights_note: rightsHelp[rights.value], top: Number(count.value)};
        if (url.value.trim()) payload.source_url = url.value.trim();
        else { payload.file_name = file.files[0].name; payload.file_data = await toBase64(file.files[0]); }
        const result = await post("/api/start-job", payload);
        addActivity(result.status === "already_running" ? "Rejoined an active video job" : "Started finding clips");
        state.homeForm = null;
        state.pendingJobId = result.job_id;
        state.progress = {stage: "queued", label: "Starting"};
        state.cancelConfirm = false;
        const measuredStart = Date.parse(result.started_at || "");
        const startedAt = Number.isFinite(measuredStart) ? measuredStart : Date.now();
        state.activeJob = {jobId: result.job_id, title: result.title || payload.source_url || payload.file_name || "Video", startedAt, stage: "queued", stageStartedAt: startedAt};
        saveActiveJob();
        renderFind();
        pollJob(result.job_id);
      } catch (error) {
        setSourceLocked(false);
        addActivity("Could not start finding clips", "error");
        showMessage("error", "The video could not be started", error.message);
      }
    }), "primary button-large");
    const chooseFile = selected => {
      if (state.activeJob && state.pendingJobId) return;
      if (!selected) return;
      url.value = "";
      try { const transfer = new DataTransfer(); transfer.items.add(selected); file.files = transfer.files; } catch {}
      fileLabel.classList.add("has-file");
      fileLabel.dataset.fileName = selected.name;
      removeFile.hidden = false;
      syncForm();
    };
    file.addEventListener("change", () => chooseFile(file.files?.[0]));
    ["dragenter", "dragover"].forEach(name => fileLabel.addEventListener(name, event => { event.preventDefault(); fileLabel.classList.add("is-dragging"); }));
    ["dragleave", "drop"].forEach(name => fileLabel.addEventListener(name, event => { event.preventDefault(); fileLabel.classList.remove("is-dragging"); }));
    fileLabel.addEventListener("drop", event => chooseFile(event.dataTransfer?.files?.[0]));

    if (active) {
      setSourceLocked(true);
      start.disabled = true;
    }

    renderRecent(view);
    showView("home");
  };

  const progressContent = (parent, progress) => {
    const current = stageIndex(progress);
    const summary = node(parent, "div", undefined, "find-stage-summary");
    node(summary, "strong", stageLabel(progress));
    node(summary, "span", current >= findStages.length ? "All stages finished" : `Stage ${Math.max(1, current)} of ${findStages.length}`);
    const track = node(parent, "div", undefined, "progress-track");
    const fill = node(track, "span", undefined, "progress-fill indeterminate");
    const stages = node(parent, "ol", undefined, "find-stages");
    findStages.forEach((item, index) => {
      const step = node(stages, "li", undefined, `${index + 1 < current ? "complete" : index + 1 === current ? "current" : ""}`);
      node(step, "span", item.label);
      if (state.activeJob?.stage === item.key && state.activeJob.stageStartedAt) node(step, "small", `Started ${formatElapsed(Date.now() - state.activeJob.stageStartedAt)} ago`);
    });
    return {fill};
  };
  const renderFind = () => {
    stopVideos();
    const view = document.getElementById("find-view");
    clear(view);
    addHint(view, "find", "You do not need to press reload. This page updates when the work is ready.");
    const panel = node(view, "section", undefined, "find-panel narrow");
    node(panel, "p", "Step 2 of 4", "eyebrow");
    const failed = state.progress?.failure;
    node(panel, "h1", failed ? "Finding clips stopped" : "Finding clips");
    if (!state.activeJob && !state.progress) {
      node(panel, "p", "Waiting for a video", "find-status");
      node(panel, "p", "Add a video first, then press Find clips to start.", "sub");
      button(panel, "Back to Add video", renderHome, "button-primary button-large");
      showView("find");
      return;
    }
    if (state.activeJob?.title) node(panel, "p", state.activeJob.title, "find-title");
    node(panel, "p", failed ? `${stageLabel(state.progress)} · stopped` : stageLabel(state.progress || {stage: "queued"}), "find-status");
    if (failed) {
      node(panel, "p", state.progress.error || "The video could not be processed.", "find-error");
      const elapsed = node(panel, "p", undefined, "find-elapsed");
      elapsed.dataset.clock = "total";
      node(elapsed, "strong", "Total elapsed: ");
      node(elapsed, "span", formatElapsed(Date.now() - Number(state.activeJob?.startedAt || Date.now())), "elapsed-value");
      const actions = node(panel, "div", undefined, "find-actions find-failure-actions");
      button(actions, "Try again", element => actionButton(element, "Starting…", async () => {
        try {
          const result = await post(`/api/retry/${encodeURIComponent(state.activeJob?.jobId || state.pendingJobId)}`, {});
          const jobId = result.job_id || state.activeJob?.jobId || state.pendingJobId;
          state.pendingJobId = jobId;
          state.cancelConfirm = false;
          state.progress = {stage: "queued", label: "Starting"};
          const measuredStart = Date.parse(result.started_at || "");
          const startedAt = Number.isFinite(measuredStart) ? measuredStart : Date.now();
          state.activeJob = {...state.activeJob, jobId, startedAt, stage: "queued", stageStartedAt: startedAt};
          saveActiveJob();
          renderFind();
          pollJob(jobId);
        } catch (error) { showMessage("error", "The video could not be restarted", error.message); }
      }), "button-primary");
      button(actions, "Back to Add video", () => { state.pendingJobId = null; state.pollingJobId = null; state.progress = null; state.cancelConfirm = false; clearActiveJob(); renderHome(); }, "button-secondary");
      button(actions, "Show details", () => showMessage("error", "What went wrong", state.progress.error || "No additional details are available.", {details: state.activeJob?.jobId || state.pendingJobId}), "button-secondary");
    } else {
      progressContent(panel, state.progress || {stage: "queued", label: "Waiting for a video"});
      const elapsed = node(panel, "p", undefined, "find-elapsed");
      elapsed.dataset.clock = "total";
      node(elapsed, "strong", "Total elapsed: ");
      node(elapsed, "span", formatElapsed(Date.now() - Number(state.activeJob?.startedAt || Date.now())), "elapsed-value");
      if (state.activeJob?.stageStartedAt && Date.now() - state.activeJob.stageStartedAt > 300000) node(panel, "p", "This stage can take a few minutes on long videos.", "find-slow-note");
      if (state.progress?.timedOut) {
        node(panel, "p", "Still working — it’s taking longer than usual. The job is still running.", "find-slow-note");
        const actions = node(panel, "div", undefined, "find-actions");
        button(actions, "Check again", () => { state.progress = {...state.progress, timedOut: false}; renderFind(); pollJob(state.pendingJobId); }, "button-primary");
      } else if (state.cancelConfirm) {
        const confirm = node(panel, "div", undefined, "cancel-confirm");
        node(confirm, "strong", "Stop finding clips?");
        button(confirm, "Yes, stop", element => actionButton(element, "Stopping…", async () => {
          try { await post(`/api/cancel/${encodeURIComponent(state.pendingJobId)}`, {}); }
          catch (error) { state.cancelConfirm = false; renderFind(); showMessage("error", "Could not stop this video", error.message); return; }
          state.pendingJobId = null; state.pollingJobId = null; state.progress = null; state.cancelConfirm = false; clearActiveJob(); addActivity("Stopped finding clips"); renderHome(); showMessage("success", "Stopped", "You can add the video again whenever you are ready.");
        }), "button-danger");
        button(confirm, "Keep going", () => { state.cancelConfirm = false; renderFind(); }, "button-secondary");
      } else {
        button(panel, "Cancel", () => { state.cancelConfirm = true; renderFind(); }, "cancel-button");
      }
    }
    showView("find");
  };
  const updateFind = progress => {
    state.progress = progress;
    rememberStage(progress);
    if (state.view === "find") renderFind();
  };
  const failFind = (job, message) => {
    state.progress = {...(job?.progress || state.progress || {}), failure: true, error: message || job?.error || "The video could not be processed."};
    rememberStage(state.progress);
    renderFind();
  };
  const handleJob = (job, data, jobId) => {
    if (!job) return false;
    updateFind({...job.progress, error: job.error});
    if (!["awaiting_review", "passed", "needs_review", "failed", "cancelled"].includes(job.state)) return false;
    state.pollingJobId = null;
    if (job.state === "awaiting_review") {
      const candidates = (data.candidates || []).filter(record => record.job_id === jobId);
      if (!candidates.length) { failFind(job, "The job finished, but no clips were created yet. Try again or check the details."); return true; }
      state.pendingJobId = null; clearActiveJob(); state.candidates = candidates; state.reviewGroupId = sourceGroupFor(candidates[0]); addActivity("Clips are ready to review"); state.selectedId = null; state.selectedJobId = null; renderReview(state.candidates);
    } else if (job.state === "failed") {
      failFind(job, job.error || "The video could not be processed. Open the details to see what happened.");
    } else if (job.state === "cancelled") {
      state.pendingJobId = null; state.progress = null; clearActiveJob(); renderHome(); showMessage("success", "Stopped", "You can add the video again whenever you are ready.");
    } else {
      state.pendingJobId = null; clearActiveJob(); state.progress = null; renderHome();
    }
    return true;
  };
  const pollJob = async jobId => {
    if (state.pollingJobId === jobId) return;
    state.pollingJobId = jobId;
    for (let tries = 0; tries < 180 && state.pendingJobId === jobId && state.pollingJobId === jobId; tries += 1) {
      await sleep(1200);
      try {
        const data = await refresh();
        const job = data.jobs.find(item => item.job_id === jobId);
        if (!job) continue;
        if (handleJob(job, data, jobId)) return;
      } catch (error) {
        setConnection(false);
        updateFind({...state.progress, label: "Connection lost, reconnecting…", connectionLost: true});
      }
    }
    if (state.pendingJobId === jobId && state.pollingJobId === jobId) {
      state.pollingJobId = null;
      state.progress = {...state.progress, timedOut: true};
      renderFind();
    }
  };
  const restoreActiveJob = data => {
    if (!state.activeJob) return false;
    const jobId = state.activeJob.jobId;
    const job = (data.jobs || []).find(item => item.job_id === jobId);
    if (!job) {
      state.pendingJobId = jobId;
      state.progress = {stage: state.activeJob.stage || "queued", label: "The job could not be found", failure: true, error: "Debate Clipper could not find this job. Open the details or go back to Add video."};
      renderFind();
      return true;
    }
    state.pendingJobId = jobId;
    state.progress = {...job.progress, error: job.error};
    rememberStage(state.progress);
    if (handleJob(job, data, jobId)) return true;
    renderFind();
    pollJob(jobId);
    return true;
  };
  const refreshActiveJob = async () => {
    const jobId = state.activeJob?.jobId || state.pendingJobId;
    if (!jobId) { renderFind(); return; }
    try {
      const data = await refresh();
      const job = (data.jobs || []).find(item => item.job_id === jobId);
      if (job) {
        state.pendingJobId = jobId;
        if (handleJob(job, data, jobId)) return;
        state.progress = {...job.progress, error: job.error};
        rememberStage(state.progress);
        renderFind();
        pollJob(jobId);
      } else {
        state.pendingJobId = jobId;
        state.progress = {stage: state.activeJob?.stage || "queued", label: "The job could not be found", failure: true, error: "Debate Clipper could not find this job. Open the details or go back to Add video."};
        renderFind();
      }
    } catch (error) { setConnection(false); showMessage("error", "Could not check this video", error.message); }
  };

  const recordForSelection = (jobId, id, records = state.candidates) => {
    const matches = records.filter(record => record.id === id && (jobId == null || record.job_id === jobId));
    return matches.length === 1 ? matches[0] : null;
  };
  const controlsFor = record => {
    if (!record) return {framing: {layout: "auto", zoom: 1, move_x: 0, move_y: 0}, caption: {size_delta: 0, vertical_delta: 0, highlight_color: "#B4F83D", style: "hormozi_glow", enabled: true}};
    if (!state.controls[reviewKey(record)]) {
      const decision = record.decision || {};
      state.controls[reviewKey(record)] = {
        framing: {...(decision.framing_controls || {layout: "auto", zoom: 1, move_x: 0, move_y: 0})},
        caption: {enabled: true, size_delta: 0, vertical_delta: 0, highlight_color: "#B4F83D", style: "hormozi_glow", ...(decision.caption_controls || {})},
      };
    }
    return state.controls[reviewKey(record)];
  };
  const mediaFor = record => {
    const source = withToken(`/api/media/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/source`);
    const proxy = withToken(`/api/media/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/proxy`);
    const clip = withToken(`/api/media/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/clip`);
    return proxy;
  };
  const configureVideo = (video, record, editing = false) => {
    const source = withToken(`/api/media/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/source`);
    const proxy = withToken(`/api/media/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/proxy`);
    const clip = withToken(`/api/media/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/clip`);
    const urls = editing ? [source, proxy, clip] : [proxy, clip, source];
    let index = 0;
    video.controls = true; video.playsInline = true; video.preload = "metadata"; video.src = urls[index];
    video.addEventListener("error", () => { if (index < urls.length - 1) { index += 1; video.src = urls[index]; } });
    video.addEventListener("loadedmetadata", () => { if (editing || !record.export && index === urls.length - 1) video.currentTime = Number(editsFor(record).start) || 0; }, {once: true});
    videos.register(video);
  };
  const scoreDetails = (parent, record) => {
    const details = node(parent, "details", undefined, "why-score");
    node(details, "summary", "Why this rating?");
    node(details, "p", "These are clues, not a promise of views. If a signal was not measured, it is left blank.", "help");
    Object.entries(scoreNames).forEach(([key, label]) => {
      const row = node(details, "div", undefined, "score-row");
      node(row, "span", label);
      const value = record.components?.[key];
      if (!measured(value)) node(row, "strong", "Not measured");
      else { node(row, "strong", `${Math.round(Number(value) * 100)}%`); }
    });
    return details;
  };
  const applyPreview = (video, overlay, controls) => {
    const framing = controls.framing;
    if (video.dataset.pinPreview !== "1") video.style.transform = `scale(${framing.zoom}) translate(${framing.move_x * -8}%, ${framing.move_y * -8}%)`;
    if (!overlay) return;
    overlay.style.fontSize = `${Math.max(16, 22 + Number(controls.caption.size_delta || 0) / 2)}px`;
    overlay.style.bottom = `${Math.max(8, 18 - Number(controls.caption.vertical_delta || 0) / 8)}%`;
    overlay.style.color = controls.caption.highlight_color || "#B4F83D";
  };
  // ---- Framing pins (Phase 4C, Sections 12.2-12.3) ----
  // Crop ratio for the default 9:16 shape is the production feed ratio
  // (config/political_lens.json regions.feed 1080x1216); the render
  // computes pin rects with dc.layout.crop_rect from the same ratio,
  // and the centre formula below is the render's own, so the preview
  // crop is the export crop.
  const FRAMING_FEED_RATIO = 1080 / 1216;
  const FRAMING_FEED_WINDOW = {left: 0, top: 509 / 1920, width: 1, height: 1216 / 1920};
  const FRAMING_SHAPE_RATIOS = {"9:16": FRAMING_FEED_RATIO, "1:1": 1, "16:9": 16 / 9};
  const defaultPinJS = t => ({t: Number(t) || 0, zoom: 1, move_x: 0, move_y: 0, preset: "auto"});
  const clonePins = pins => (pins || []).map(pin => ({...pin}));
  const pinLabelJS = pin => ({auto: "Auto", wide: "Wide", both: "Both", a: Number(pin.zoom) >= 1.5 ? "A Close" : "Person A", b: Number(pin.zoom) >= 1.5 ? "B Close" : "Person B", custom: "Custom"})[pin.preset] || "Custom";
  const activePinIndex = (pins, t) => { let index = 0; (pins || []).forEach((pin, i) => { if (Number(pin.t) <= Number(t) + 1e-6) index = i; }); return index; };
  const framingIsDirty = session => Boolean(session?.framing?.touched && (JSON.stringify(session.framing.pins) !== JSON.stringify(session.framing.savedPins || []) || session.framing.shape !== session.framing.savedShape));
  const cropRectJS = (sourceW, sourceH, ratio, centerX, centerY, zoom) => {
    const z = Math.max(1, Number(zoom) || 1);
    let cropH = Math.min(sourceH, sourceW / ratio) / z;
    let cropW = cropH * ratio;
    if (cropW > sourceW) { cropW = sourceW; cropH = cropW / ratio; }
    const x = Math.min(Math.max(0, centerX - cropW / 2), Math.max(0, sourceW - cropW));
    const y = Math.min(Math.max(0, centerY - cropH / 2), Math.max(0, sourceH - cropH));
    return {x, y, w: cropW, h: cropH};
  };
  const pinRectJS = (record, pin, shape) => {
    const sourceW = Number(record.source?.width) || 1920;
    const sourceH = Number(record.source?.height) || 1080;
    const ratio = FRAMING_SHAPE_RATIOS[shape] || FRAMING_FEED_RATIO;
    const centerX = sourceW / 2 + Number(pin.move_x || 0) * sourceW * .25;
    const centerY = sourceH / 2 + Number(pin.move_y || 0) * sourceH * .25;
    return cropRectJS(sourceW, sourceH, ratio, centerX, centerY, Number(pin.zoom) || 1);
  };
  const mediaOffsetFor = (video, record) => {
    const bounds = currentEditsFor(record);
    const clipLength = Number(bounds.end) - Number(bounds.start);
    const mediaDuration = Number(video?.duration);
    return Number.isFinite(mediaDuration) && mediaDuration > 0 && Math.abs(mediaDuration - clipLength) < 2 ? 0 : Number(bounds.start);
  };
  const clipTimeOf = (video, record) => {
    const bounds = currentEditsFor(record);
    const duration = Math.max(0, Number(bounds.end) - Number(bounds.start));
    return {t: Math.min(duration, Math.max(0, Number(video.currentTime || 0) - mediaOffsetFor(video, record))), duration};
  };
  const applyPinPreview = (record, video) => {
    const session = state.editSession;
    if (!video || !session?.framing || session.recordKey !== reviewKey(record)) return;
    const shell = video.closest(".video-shell");
    if (!shell) return;
    const {t} = clipTimeOf(video, record);
    const pins = session.framing.pins;
    const pin = pins[activePinIndex(pins, t)] || pins[0] || defaultPinJS(0);
    const shape = session.framing.shape || "9:16";
    const rect = pinRectJS(record, pin, shape);
    const sourceW = Number(record.source?.width) || 1920;
    const sourceH = Number(record.source?.height) || 1080;
    const win = shape === "9:16" ? FRAMING_FEED_WINDOW : {left: 0, top: 0, width: 1, height: 1};
    let guide = shell.querySelector(".framing-safe-guide");
    if (shell.classList.contains("framing-active")) {
      if (!guide) { guide = document.createElement("div"); guide.className = "framing-safe-guide"; shell.appendChild(guide); }
      guide.style.left = `${100 * (win.left + win.width * .07)}%`;
      guide.style.width = `${100 * win.width * .86}%`;
      guide.style.top = `${100 * (win.top + win.height * .07)}%`;
      guide.style.height = `${100 * win.height * .86}%`;
    } else if (guide) guide.remove();
    if (!session.framing.touched && !session.framing.savedPins) return;
    shell.style.aspectRatio = shape === "9:16" ? "" : shape.replace(":", " / ");
    video.dataset.pinPreview = "1";
    video.style.position = "absolute";
    video.style.width = `${100 * win.width * sourceW / rect.w}%`;
    video.style.height = `${100 * win.height * sourceH / rect.h}%`;
    video.style.left = `${100 * (win.left - win.width * rect.x / rect.w)}%`;
    video.style.top = `${100 * (win.top - win.height * rect.y / rect.h)}%`;
    video.style.objectFit = "fill";
    video.style.transform = "none";
  };
  const clearPinPreview = video => {
    if (!video) return;
    delete video.dataset.pinPreview;
    ["position", "width", "height", "left", "top", "objectFit", "transform"].forEach(prop => { video.style[prop] = ""; });
    const shell = video.closest(".video-shell");
    if (shell) { shell.style.aspectRatio = ""; shell.classList.remove("framing-active"); shell.querySelector(".framing-safe-guide")?.remove(); }
  };
  const setFramingStatus = record => {
    const panel = document.querySelector("#review-view .edit-panel");
    const status = panel?.querySelector(".framing-save-status");
    if (!status) return;
    const framing = state.editSession?.framing;
    if (!framing) return;
    status.textContent = framing.saveState === "saving" ? "Saving…" : framing.saveState === "saved" ? "Saved ✓" : framing.saveState === "error" ? "Could not save this pin — Try again" : "";
    status.classList.toggle("is-error", framing.saveState === "error");
  };
  const framingSave = async record => {
    const session = state.editSession;
    if (!session?.framing || session.recordKey !== reviewKey(record)) return;
    const framing = session.framing;
    framing.saveState = "saving"; setFramingStatus(record);
    try {
      const data = await saveDecision(record, "save");
      storeDecision(record, data);
      framing.savedPins = clonePins(framing.pins);
      framing.savedShape = framing.shape;
      framing.saveState = "saved";
    } catch { framing.saveState = "error"; }
    setFramingStatus(record);
  };
  const scheduleFramingSave = (record, immediate = false) => {
    const session = state.editSession;
    if (!session?.framing) return;
    session.framing.touched = true;
    clearTimeout(session.framing.saveTimer);
    session.framing.saveTimer = setTimeout(() => framingSave(record), immediate ? 60 : 650);
  };

  const editsFor = record => ({start: Number(record.decision?.edits?.start ?? record.start), end: Number(record.decision?.edits?.end ?? record.end)});
  const saveDecision = async (record, action, extras = {}) => {
    const controls = controlsFor(record);
    const framingSession = state.editSession?.recordKey === reviewKey(record) ? state.editSession : null;
    const framingExtras = framingSession?.framing?.touched ? {framing_pins: framingSession.framing.pins, framing_shape: framingSession.framing.shape} : {};
    const payload = {job_id: record.job_id, candidate_id: record.id, action, headline: currentHeadlineFor(record), edits: currentEditsFor(record), framing_controls: controls.framing, caption_controls: controls.caption, ...framingExtras, ...extras};
    return post("/api/decisions", payload);
  };

  const reviewKey = record => `${record.job_id}/${record.id}`;
  const attemptFor = record => state.reviewExports.find(item => item.job_id === record.job_id && item.candidate_id === record.id) || record.export_attempt;
  const runningExport = () => state.reviewExports.find(item => item.status === "exporting");
  const rememberAttempt = attempt => {
    if (!attempt) return;
    state.reviewExports = [attempt, ...state.reviewExports.filter(item => item.export_id !== attempt.export_id)];
  };
  const storeDecision = (record, data) => {
    const current = state.candidates.find(item => reviewKey(item) === reviewKey(record)) || record;
    [record, current].forEach(item => {
      const previousAction = item.decision?.action;
      item.decision = {...item.decision, ...data, edits: {...item.decision?.edits, ...data.edits}};
      if (data.action === "save" && ["approve", "reject"].includes(previousAction)) item.decision.action = previousAction;
      else if (data.action === "save") delete item.decision.action;
      if (data.edit_revision) item.edit_revision = data.edit_revision;
      item.uiState = data.action === "approve" ? "Approved" : data.action === "reject" ? "Rejected" : item.uiState;
    });
  };
  const controlsChanged = record => {
    const current = controlsFor(record);
    const saved = record.decision || {};
    const framing = {layout: "auto", zoom: 1, move_x: 0, move_y: 0, ...saved.framing_controls};
    const caption = {enabled: true, size_delta: 0, vertical_delta: 0, highlight_color: "#B4F83D", style: "hormozi_glow", ...saved.caption_controls};
    return Object.keys(framing).some(key => framing[key] !== current.framing[key]) || Object.keys(caption).some(key => caption[key] !== current.caption[key]);
  };
  const exportButtonFor = record => {
    const pending = state.reviewPending[reviewKey(record)];
    const attempt = attemptFor(record);
    const active = runningExport();
    if (pending === "export" || attempt?.status === "exporting") return {label: "Exporting…", disabled: true, kind: "working", attempt};
    const exported = attempt?.status === "exported" ? attempt.export : record.export;
    const revision = attempt?.status === "exported" ? attempt.edit_revision : exported?.edit_revision;
    if (attempt && ["failed", "not_finished"].includes(attempt.status)) return {label: attempt.status === "failed" ? "Export failed — Try again" : "Not finished — Try again", kind: "failed", attempt};
    if (exported && attempt?.status === "exported" && !controlsChanged(record) && (!revision || record.edit_revision === undefined || revision === record.edit_revision)) return {label: "Exported ✓", kind: "exported", exported, attempt};
    if (active) return {label: "Another export is already running", disabled: true, kind: "blocked", note: "View the running export below.", attempt: active};
    return {label: "Export", kind: "ready", note: exported ? (revision ? "Edited since export" : "Previous export available") : ""};
  };
  const groupProgressFor = records => {
    const reviewed = records.filter(item => ["approve", "Approved", "reject", "Rejected"].includes(reviewActionFor(item))).length;
    const approved = records.filter(item => ["approve", "Approved"].includes(reviewActionFor(item))).length;
    const exported = records.filter(item => stateFor(item) === "Exported").length;
    return `${reviewed} of ${records.length} reviewed — ${approved} approved · ${exported} exported`;
  };
  const syncReviewState = () => {
    const view = document.getElementById("review-view");
    view.querySelectorAll(".clip-row").forEach(row => {
      const record = state.candidates.find(item => reviewKey(item) === row.dataset.reviewKey);
      if (!record) return;
      const status = stateFor(record);
      const badge = row.querySelector(".status-badge");
      badge.textContent = status; badge.hidden = status === "Not reviewed";
      badge.className = `status-badge status-${stateClass(status)}`;
    });
    view.querySelectorAll(".source-group").forEach(group => {
      const records = state.candidates.filter(item => sourceGroupFor(item) === group.dataset.groupId && !state.jobs.some(job => job.job_id === item.job_id && job.is_test));
      group.querySelector(".group-progress").textContent = groupProgressFor(records);
    });
    const actions = view.querySelector(".review-actions");
    if (!actions) return;
    const record = state.candidates.find(item => reviewKey(item) === actions.dataset.reviewKey);
    if (!record) return;
    const pending = state.reviewPending[reviewKey(record)];
    const exported = exportButtonFor(record);
    actions.querySelectorAll(".review-action").forEach(element => {
      const action = element.dataset.action;
      element.disabled = Boolean(pending) || (action === "export" && Boolean(exported.disabled));
      element.textContent = action === "export" ? exported.label : pending === action ? (action === "reject" ? "Rejecting…" : "Saving…") : action[0].toUpperCase() + action.slice(1);
      element.classList.toggle("is-busy", pending === action || (action === "export" && exported.kind === "working"));
      if (action === "export") element.className = `export review-action export-${exported.kind}${exported.kind === "working" ? " is-busy" : ""}`;
    });
    const feedback = actions.querySelector(".review-feedback");
    const message = state.reviewFeedback[reviewKey(record)];
    feedback.textContent = message?.text || exported.note || "";
    feedback.classList.toggle("is-error", message?.kind === "error");
    const link = actions.querySelector(".view-export");
    link.hidden = !exported.attempt || !["working", "blocked"].includes(exported.kind);
    link.onclick = () => openReviewExport(exported.attempt);
  };

  const cloneEditValue = value => {
    try { return structuredClone(value); }
    catch { return JSON.parse(JSON.stringify(value)); }
  };
  const currentHeadlineFor = record => state.editSession?.recordKey === reviewKey(record) ? state.editSession.headline : titleFor(record);
  const currentEditsFor = record => state.editSession?.recordKey === reviewKey(record) ? state.editSession.edits : editsFor(record);
  const editIsDirty = record => {
    const session = state.editSession;
    return Boolean(session && session.recordKey === reviewKey(record) && (JSON.stringify(controlsFor(record)) !== JSON.stringify(session.controls) || session.headline !== session.savedHeadline || JSON.stringify(session.edits) !== JSON.stringify(session.savedEdits) || framingIsDirty(session)));
  };
  const beginEditSession = record => {
    const headline = record.decision && Object.prototype.hasOwnProperty.call(record.decision, "headline") ? record.decision.headline : titleFor(record);
    const edits = editsFor(record);
    state.editSession = {recordKey: reviewKey(record), controls: cloneEditValue(controlsFor(record)), savedHeadline: headline, headline, savedEdits: cloneEditValue(edits), edits: cloneEditValue(edits), trimError: "", savedLoadState: "loading", savedLoadError: ""};
    const savedPins = Array.isArray(record.decision?.framing_pins) && record.decision.framing_pins.length ? clonePins(record.decision.framing_pins) : null;
    state.editSession.framing = {pins: savedPins ? clonePins(savedPins) : [defaultPinJS(0)], savedPins, shape: record.decision?.framing_shape || "9:16", savedShape: record.decision?.framing_shape || "9:16", activeT: 0, touched: false, saveState: savedPins ? "saved" : "", saveTimer: null};
  };
  const loadSavedDecisionFresh = async record => {
    const key = reviewKey(record);
    try {
      const fresh = await getFreshCandidate(record);
      if (!state.editing || state.editSession?.recordKey !== key) return;
      applyFreshCandidate(record, fresh);
      beginEditSession(record);
      state.editSession.savedLoadState = "loaded";
      refreshEditPanel(record);
    } catch (error) {
      if (state.editSession?.recordKey !== key) return;
      state.editSession.savedLoadState = "error";
      state.editSession.savedLoadError = error.message || "";
      refreshEditPanel(record);
    }
  };
  const showSavedHeadlineReadback = () => {
    const readback = state.savedHeadlineReadback;
    const view = document.getElementById("review-view");
    if (!readback || !view) return;
    view.querySelector(".saved-headline-readback")?.remove();
    const layout = view.querySelector(".review-layout");
    if (!layout) return;
    const line = document.createElement("p");
    line.className = "saved-headline-readback";
    line.setAttribute("role", "status");
    line.textContent = savedHeadlineText(readback.headline);
    layout.before(line);
  };
  const restoreEditSession = record => {
    if (state.editSession?.recordKey !== reviewKey(record)) return;
    state.controls[reviewKey(record)] = cloneEditValue(state.editSession.controls);
    state.editSession.headline = state.editSession.savedHeadline;
    state.editSession.edits = cloneEditValue(state.editSession.savedEdits);
    state.editSession.trimError = "";
    if (state.editSession.framing) { const framing = state.editSession.framing; framing.pins = framing.savedPins ? clonePins(framing.savedPins) : [defaultPinJS(0)]; framing.shape = framing.savedShape; framing.touched = false; framing.saveState = framing.savedPins ? "saved" : ""; }
  };
  const preserveVideoState = (video, snapshot) => {
    if (!video || !snapshot) return;
    if (Number.isFinite(snapshot.time) && Math.abs(Number(video.currentTime || 0) - snapshot.time) > .03) video.currentTime = snapshot.time;
    if (snapshot.paused) video.pause();
    else video.play().catch(() => {});
  };
  const refreshEditPanel = (record, options = {}) => {
    const layout = document.querySelector("#review-view .review-layout");
    if (!layout || layout.querySelector(".review-actions")?.dataset.reviewKey !== reviewKey(record)) return;
    const video = layout.querySelector("video");
    const snapshot = video ? {time: Number(video.currentTime), paused: video.paused} : null;
    const previousPanel = layout.querySelector(".edit-panel");
    const panelScrollTop = previousPanel?.scrollTop || 0;
    layout.querySelector(".edit-panel")?.remove();
    renderEditPanel(layout, record, video, null);
    const panel = layout.querySelector(".edit-panel");
    if (panel) {
      const restorePanelScroll = () => {
        panel.scrollTop = panelScrollTop;
        if (!options.focusGroup) return;
        const group = panel.querySelector(`.edit-accordion-group.open .edit-accordion-trigger`);
        if (!group) return;
        const panelRect = panel.getBoundingClientRect();
        const groupRect = group.getBoundingClientRect();
        if (groupRect.top < panelRect.top + 12) panel.scrollTop -= panelRect.top + 12 - groupRect.top;
        else if (groupRect.bottom > panelRect.bottom - 12) panel.scrollTop += groupRect.bottom - (panelRect.bottom - 12);
      };
      restorePanelScroll();
      if (options.focusGroup) requestAnimationFrame(restorePanelScroll);
    }
    if (video && !layout.querySelector(".edit-playback")) renderEditPlayback(layout.querySelector(".review-stage"), video, record);
    preserveVideoState(video, snapshot);
  };
  const removeEditPlayback = layout => {
    layout?.querySelector(".edit-playback")?.remove();
    layout?.querySelector(".edit-play-overlay")?.remove();
  };
  const closeReviewEdit = record => {
    const layout = document.querySelector("#review-view .review-layout");
    if (!layout || layout.querySelector(".review-actions")?.dataset.reviewKey !== reviewKey(record)) return;
    state.editing = false; state.editSavePending = false; state.editDiscardConfirm = false; state.editSession = null;
    layout.classList.remove("editing");
    clearPinPreview(layout.querySelector("video"));
    layout.querySelector(".edit-panel")?.remove();
    removeEditPlayback(layout);
    syncReviewState();
  };
  const requestCancelEdit = record => {
    if (editIsDirty(record)) { state.editDiscardConfirm = true; refreshEditPanel(record); }
    else closeReviewEdit(record);
  };
  const setEditSaveUi = (record, message = "") => {
    const panel = document.querySelector("#review-view .edit-panel");
    if (!panel) return;
    panel.querySelectorAll(".edit-save-button").forEach(save => { save.disabled = state.editSavePending; save.textContent = state.editSavePending ? "Saving…" : "Save & Done"; });
    const status = panel.querySelector(".edit-save-status");
    if (status) { status.textContent = message || (state.editSavePending ? "Saving…" : ""); status.classList.toggle("is-error", message.startsWith("Save failed")); }
  };
  const saveEditAndDone = async record => {
    if (state.editSavePending) return;
    const headlineInput = document.querySelector("#review-view .edit-headline-field input");
    if (headlineInput && state.editSession?.recordKey === reviewKey(record)) state.editSession.headline = headlineInput.value;
    const edits = currentEditsFor(record);
    const sourceDuration = Number(record.source?.duration);
    const maximum = Number.isFinite(sourceDuration) && sourceDuration > 0 ? sourceDuration : Math.max(Number(record.end) || 0, Number(edits.end) || 0);
    if (state.editSession?.trimError || !Number.isFinite(Number(edits.start)) || !Number.isFinite(Number(edits.end)) || Number(edits.start) < 0 || Number(edits.end) > maximum || Number(edits.start) >= Number(edits.end)) {
      if (state.editSession?.recordKey === reviewKey(record)) state.editSession.trimError = "Start must be before end and stay inside the source video.";
      setEditSaveUi(record, "Save failed. Start must be before end and stay inside the source video.");
      return;
    }
    state.editSavePending = true;
    setEditSaveUi(record);
    try {
      const data = await saveDecision(record, "save");
      storeDecision(record, data);
      let readBackHeadline = null;
      try {
        const fresh = await getFreshCandidate(record);
        applyFreshCandidate(record, fresh);
        if (fresh.decision && Object.prototype.hasOwnProperty.call(fresh.decision, "headline")) readBackHeadline = fresh.decision.headline;
      } catch {}
      if (readBackHeadline !== null) state.savedHeadlineReadback = {recordKey: reviewKey(record), headline: readBackHeadline};
      addActivity("Edit changes saved");
      showMessage("success", "Saved", readBackHeadline !== null ? `${savedHeadlineText(readBackHeadline)} — read back from the server.` : "Your edit changes were saved.");
      closeReviewEdit(record);
      showSavedHeadlineReadback();
    } catch (error) {
      state.editSavePending = false;
      setEditSaveUi(record, `Save failed. ${error.message} Try again.`);
      addActivity("Edit save failed", "error");
      showMessage("error", "Save failed", `${error.message} Try again.`);
    }
  };
  const toggleReviewEdit = (record, editing) => {
    const layout = document.querySelector("#review-view .review-layout");
    if (!layout || layout.querySelector(".review-actions")?.dataset.reviewKey !== reviewKey(record)) return;
    if (!editing) { requestCancelEdit(record); return; }
    state.editing = true; state.editGroup = "speaker"; state.editDiscardConfirm = false; state.editSavePending = false;
    beginEditSession(record);
    layout.classList.add("editing");
    renderEditPlayback(layout.querySelector(".review-stage"), layout.querySelector("video"), record);
    renderEditPanel(layout, record, layout.querySelector("video"), null);
    applyPinPreview(record, layout.querySelector("video"));
    loadSavedDecisionFresh(record);
  };

  const renderEditPlayback = (stage, video, record) => {
    if (!stage || !video) return;
    stage.querySelector(".edit-playback")?.remove();
    stage.querySelector(".edit-play-overlay")?.remove();
    const shell = stage.querySelector(".video-shell");
    if (!shell) return;
    const overlay = button(shell, "Play", () => { if (video.paused) video.play().catch(() => {}); else video.pause(); }, "edit-play-overlay");
    overlay.hidden = !video.paused;
    overlay.setAttribute("aria-label", "Play/Pause");
    const controls = node(stage, "div", undefined, "edit-playback");
    const transport = node(controls, "div", undefined, "edit-playback-transport");
    const play = button(transport, "Play", () => { if (video.paused) video.play().catch(() => {}); else video.pause(); }, "edit-play-toggle button-primary");
    play.setAttribute("aria-label", "Play/Pause");
    const back = button(transport, "−5 seconds", () => { const bounds = currentEditsFor(record); video.currentTime = Math.max(Number(bounds.start) || 0, Number(video.currentTime || 0) - 5); }, "edit-skip");
    const forward = button(transport, "+5 seconds", () => { const bounds = currentEditsFor(record); video.currentTime = Math.min(Number(bounds.end) || Number(video.duration) || Infinity, Number(video.currentTime || 0) + 5); }, "edit-skip");
    const initialBounds = currentEditsFor(record);
    const slider = input(controls, "range", 0); slider.className = "edit-seek"; slider.min = 0; slider.max = Math.max(1, Number(initialBounds.end) - Number(initialBounds.start)); slider.step = .01; slider.setAttribute("aria-label", "Seek through the clip");
    const time = node(controls, "div", "0:00 / 0:00", "edit-time");
    const update = () => {
      const bounds = currentEditsFor(record);
      const start = Number(bounds.start) || 0;
      const end = Number(bounds.end) || Number(video.duration) || start;
      const current = Math.max(0, Math.min(Math.max(0, end - start), Number(video.currentTime || start) - start));
      slider.value = String(current);
      time.textContent = `${fmtTime(current)} / ${fmtTime(Math.max(0, end - start))}`;
      const paused = video.paused;
      play.textContent = paused ? "Play" : "Pause";
      overlay.textContent = paused ? "Play" : "Pause";
      overlay.hidden = !paused;
    };
    slider.addEventListener("input", () => { const bounds = currentEditsFor(record); video.currentTime = (Number(bounds.start) || 0) + Number(slider.value); update(); });
    ["play", "pause", "timeupdate", "loadedmetadata", "durationchange", "seeking", "seeked"].forEach(eventName => video.addEventListener(eventName, update));
    update();
  };

  // ---- Captions (Phase 4D, Section 12.5) ----
  // The Edit preview overlay shows the clip's OWN caption cues, built by
  // the production caption builder through /caption-cues with the clip's
  // saved settings applied, so the words, timing, size and position on
  // screen are the export's. The overlay never appears in plain Review,
  // never over a finished export (its captions are baked into the file),
  // and never invents words when cues are unavailable.
  const CAPTION_SWATCHES = [["#B4F83D", "Green"], ["#FFE14D", "Yellow"], ["#FF7777", "Red"], ["#FFFFFF", "White"]];
  const CAPTION_POSITION_PRESETS = [[-300, "Top"], [0, "Middle"], [300, "Bottom"]];
  const CAPTION_EMPHASIS_WORDS = new Set(["no", "not", "never", "none", "nothing"]);
  const captionState = {record: null, video: null, cues: null, key: "", loading: false, failed: false, timer: null, eventIndex: -1, groupKey: "", dyTouched: false, exportMedia: null};
  const captionControls = record => controlsFor(record).caption;
  const captionEffectiveDy = record => {
    const caption = captionControls(record);
    if (captionState.dyTouched || record.decision?.caption_controls) return Number(caption.vertical_delta || 0);
    return captionState.cues ? Number(captionState.cues.dy || 0) : Number(caption.vertical_delta || 0);
  };
  const captionCuesKey = record => {
    const edits = currentEditsFor(record);
    const caption = captionControls(record);
    return `${reviewKey(record)}|${caption.style}|${caption.size_delta}|${edits.start}|${edits.end}`;
  };
  const loadCaptionCues = async (record, force = false) => {
    const key = captionCuesKey(record);
    if (!force && captionState.key === key && (captionState.cues || captionState.loading)) return;
    captionState.key = key; captionState.cues = null; captionState.failed = false; captionState.loading = true; captionState.eventIndex = -1;
    renderCaptionOverlay();
    try {
      const edits = currentEditsFor(record);
      const caption = captionControls(record);
      const data = await get(`/api/candidates/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/caption-cues?start=${encodeURIComponent(edits.start)}&end=${encodeURIComponent(edits.end)}&style=${encodeURIComponent(caption.style)}&size_delta=${encodeURIComponent(caption.size_delta)}`);
      if (captionState.key !== key) return;
      captionState.cues = data;
    } catch { if (captionState.key === key) captionState.failed = true; }
    if (captionState.key === key) { captionState.loading = false; renderCaptionOverlay(); refreshCaptionNote(); }
  };
  const mediaIsExport = video => String(video?.currentSrc || "").includes("/clip");
  const ensureCaptionOverlay = video => {
    const shell = video?.closest(".video-shell");
    if (!shell) return null;
    let el = shell.querySelector(".caption-preview");
    if (!el) {
      el = node(shell, "div", undefined, "caption-preview");
      el.setAttribute("aria-hidden", "true");
      el.addEventListener("pointerdown", event => startCaptionDrag(event));
    }
    return el;
  };
  const captionShapeTouched = () => {
    const session = state.editSession;
    return Boolean(session?.framing?.touched || session?.framing?.savedPins) && (session?.framing?.shape || "9:16") !== "9:16";
  };
  const renderCaptionOverlay = () => {
    const {video, record} = captionState;
    if (!video || !record || !video.isConnected) return;
    const el = ensureCaptionOverlay(video);
    if (!el) return;
    const caption = captionControls(record);
    const cues = captionState.cues;
    const hide = () => { el.style.display = "none"; captionState.eventIndex = -1; captionState.groupKey = ""; };
    if (!state.editing || !caption.enabled || captionState.loading || !cues?.available || mediaIsExport(video)) { hide(); return; }
    const {t} = clipTimeOf(video, record);
    const events = cues.events || [];
    const idx = events.findIndex(each => t >= each.start && t < each.end);
    if (idx < 0) { hide(); return; }
    const ev = events[idx];
    const group = (cues.groups || [])[ev.group];
    if (!group) { hide(); return; }
    el.style.display = "";
    const centreY = Number(cues.slot?.y || 1112) + captionEffectiveDy(record);
    const topFrac = captionShapeTouched() ? (centreY - Number(cues.feed?.y || 0)) / Number(cues.feed?.h || 1216) : centreY / Number(cues.canvas?.h || 1920);
    el.style.top = `${Math.min(97, Math.max(3, topFrac * 100))}%`;
    const shellW = el.parentElement?.clientWidth || 390;
    const fsBase = Number(cues.font_size || 110);
    const fsLive = cues.style === "gravitas" ? Number(ev.fs || fsBase) : Number(ev.fs || fsBase) * (110 + Number(caption.size_delta || 0)) / fsBase;
    el.style.fontSize = `${Math.max(9, shellW * fsLive / Number(cues.canvas?.w || 1080))}px`;
    el.dataset.look = cues.style || "hormozi_glow";
    const groupKey = `${ev.group}|${caption.highlight_color}|${cues.style}`;
    if (idx === captionState.eventIndex && groupKey === captionState.groupKey) return;
    captionState.eventIndex = idx; captionState.groupKey = groupKey;
    el.replaceChildren();
    let emphasisUsed = false;
    group.word_ids.forEach((wordId, i) => {
      if ((group.line_breaks || []).includes(i)) el.appendChild(document.createElement("br"));
      const word = cues.words[String(wordId)];
      if (!word) return;
      const isActive = wordId === ev.active_word;
      const span = node(el, "span", word.display ?? word.text, "caption-word");
      if (cues.style === "gravitas") { span.style.color = cues.base_color || "#FFFFFF"; return; }
      const plain = String(word.display ?? word.text).toLowerCase().replace(/[.,]+$/, "");
      const emphasis = !isActive && !emphasisUsed && (CAPTION_EMPHASIS_WORDS.has(plain) || /\d/.test(plain));
      emphasisUsed = emphasisUsed || emphasis;
      if (isActive) {
        span.style.color = caption.highlight_color || "#B4F83D";
        span.classList.add("caption-word-active");
        if (cues.style === "hormozi_glow") span.style.textShadow = `0 0 14px ${caption.highlight_color || "#B4F83D"}, 0 0 5px ${caption.highlight_color || "#B4F83D"}, 0 2px 0 #000`;
      } else span.style.color = emphasis ? (cues.emphasis_color || "#FF3B30") : (cues.base_color || "#FFFFFF");
    });
  };
  const startCaptionDrag = event => {
    const {video, record} = captionState;
    const cues = captionState.cues;
    if (!video || !record || !cues?.available || !state.editing) return;
    if (!captionControls(record).enabled || mediaIsExport(video)) return;
    event.preventDefault(); event.stopPropagation();
    const el = event.currentTarget;
    const shell = video.closest(".video-shell");
    if (!shell) return;
    const caption = captionControls(record);
    if (!record.decision?.caption_controls && !captionState.dyTouched) caption.vertical_delta = Math.round(captionEffectiveDy(record));
    captionState.dyTouched = true;
    const startY = event.clientY;
    const startDelta = Number(caption.vertical_delta || 0);
    const span = captionShapeTouched() ? Number(cues.feed?.h || 1216) : Number(cues.canvas?.h || 1920);
    el.setPointerCapture?.(event.pointerId);
    const move = moveEvent => {
      const deltaPx = (moveEvent.clientY - startY) / Math.max(1, shell.clientHeight) * span;
      caption.vertical_delta = Math.max(-320, Math.min(320, Math.round(startDelta + deltaPx)));
      renderCaptionOverlay();
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      refreshEditPanel(record);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
  };
  const startCaptionPreview = (record, video) => {
    if (captionState.record && reviewKey(captionState.record) !== reviewKey(record)) { captionState.dyTouched = false; captionState.eventIndex = -1; captionState.groupKey = ""; }
    captionState.record = record; captionState.video = video;
    if (captionState.timer) clearInterval(captionState.timer);
    captionState.timer = setInterval(() => {
      if (!state.editing || captionState.video !== video || !video.isConnected) { clearInterval(captionState.timer); captionState.timer = null; return; }
      renderCaptionOverlay();
      const isExport = mediaIsExport(video);
      if (isExport !== captionState.exportMedia) { captionState.exportMedia = isExport; refreshCaptionNote(); }
    }, 100);
    loadCaptionCues(record);
    renderCaptionOverlay();
  };
  const refreshCaptionNote = () => {
    const panel = document.querySelector("#review-view .edit-panel");
    const noteEl = panel?.querySelector(".caption-cue-note");
    if (!noteEl || !captionState.record) return;
    if (!captionControls(captionState.record).enabled) noteEl.textContent = "Captions are off for this clip. The export will have no captions.";
    else if (captionState.exportMedia) noteEl.textContent = "You are watching the exported file — its captions are baked into the picture, so no separate preview is drawn over it.";
    else if (captionState.loading) noteEl.textContent = "Loading caption preview…";
    else if (captionState.failed || (captionState.cues && !captionState.cues.available)) noteEl.textContent = "Caption preview is not available for this clip. Captions will be checked on Export.";
    else noteEl.textContent = "Preview shows this clip's own captions, exactly as Export will draw them.";
  };
  const buildCaptionsGroup = (body, record, video, controls) => {
    startCaptionPreview(record, video);
    const caption = controls.caption;
    const toggleSection = node(body, "section", undefined, "edit-option");
    node(toggleSection, "h3", "Captions");
    node(toggleSection, "p", "Show this clip's own words on the video.");
    const toggleRow = node(toggleSection, "div", undefined, "choice-row");
    const toggle = button(toggleRow, caption.enabled ? "Captions on" : "Captions off", () => { caption.enabled = !caption.enabled; renderCaptionOverlay(); refreshEditPanel(record); }, `choice caption-toggle${caption.enabled ? " active" : ""}`);
    toggle.setAttribute("aria-pressed", String(Boolean(caption.enabled)));
    if (!caption.enabled) {
      node(body, "p", "Captions are off for this clip. The export will have no captions.", "caption-cue-note");
      return;
    }
    const sizeSection = node(body, "section", undefined, "edit-option");
    node(sizeSection, "h3", "Caption size");
    node(sizeSection, "p", "Drag the slider — the words on the video change size as you move it.");
    const sizeRow = node(sizeSection, "div", undefined, "caption-size-row");
    const slider = input(sizeRow, "range");
    slider.className = "caption-size-slider";
    slider.min = "-30"; slider.max = "30"; slider.step = "1"; slider.value = String(Number(caption.size_delta || 0));
    slider.setAttribute("aria-label", "Caption size");
    const sizeValue = node(sizeRow, "span", `${Math.round((110 + Number(caption.size_delta || 0)) / 110 * 100)}%`, "caption-size-value");
    slider.addEventListener("input", () => {
      caption.size_delta = Number(slider.value);
      sizeValue.textContent = `${Math.round((110 + Number(caption.size_delta)) / 110 * 100)}%`;
      renderCaptionOverlay();
    });
    slider.addEventListener("change", () => loadCaptionCues(record, true));
    const lookSection = node(body, "section", undefined, "edit-option");
    node(lookSection, "h3", "Caption look");
    node(lookSection, "p", "The button shows the look. The words on the video change with it.");
    const looks = node(lookSection, "div", undefined, "choice-row");
    [["hormozi_glow", "Bold"], ["gravitas", "Calm"], ["karaoke_lite", "Light"]].forEach(([value, label]) => {
      const lookButton = button(looks, label, () => { caption.style = value; captionState.eventIndex = -1; loadCaptionCues(record, true); refreshEditPanel(record); }, `choice caption-look caption-look-${value}${caption.style === value ? " active" : ""}`);
      lookButton.dataset.look = value;
    });
    const colorSection = node(body, "section", undefined, "edit-option");
    node(colorSection, "h3", "Highlight colour");
    node(colorSection, "p", "This colour marks only the word being spoken.");
    const colors = node(colorSection, "div", undefined, "choice-row caption-swatches");
    CAPTION_SWATCHES.forEach(([value, label]) => {
      const swatch = button(colors, undefined, () => {
        caption.highlight_color = value;
        colors.querySelectorAll(".caption-swatch").forEach(each => each.classList.toggle("active", each.dataset.color === value));
        captionState.groupKey = "";
        renderCaptionOverlay();
      }, `caption-swatch${caption.highlight_color === value ? " active" : ""}`);
      swatch.style.background = value;
      swatch.dataset.color = value;
      swatch.title = label;
      swatch.setAttribute("aria-label", `Highlight colour ${label}`);
    });
    const posSection = node(body, "section", undefined, "edit-option");
    node(posSection, "h3", "Caption position");
    node(posSection, "p", "Pick a place, or drag the words on the video up or down.");
    const positions = node(posSection, "div", undefined, "choice-row");
    CAPTION_POSITION_PRESETS.forEach(([value, label]) => {
      button(positions, label, () => { caption.vertical_delta = value; captionState.dyTouched = true; renderCaptionOverlay(); refreshEditPanel(record); }, `choice caption-position${Math.abs(Number(caption.vertical_delta || 0) - value) <= 40 ? " active" : ""}`);
    });
    node(body, "p", "", "caption-cue-note");
    refreshCaptionNote();
  };

  const renderEditGroupContent = (body, groupName, record, video, overlay, controls) => {
    if (video) {
      applyPinPreview(record, video);
      const shell = video.closest(".video-shell");
      if (groupName !== "framing") { shell?.querySelector(".framing-safe-guide")?.remove(); shell?.classList.remove("framing-active"); }
      if (!video.dataset.pinWatch) {
        video.dataset.pinWatch = "1";
        video.addEventListener("timeupdate", () => {
          const session = state.editSession;
          if (!state.editing || !session?.framing || session.recordKey !== reviewKey(record)) return;
          const {t} = clipTimeOf(video, record);
          const idx = activePinIndex(session.framing.pins, t);
          if (String(idx) !== video.dataset.pinIdx) {
            video.dataset.pinIdx = String(idx);
            applyPinPreview(record, video);
            const pin = session.framing.pins[idx];
            const header = document.querySelector("#review-view .framing-pin-header");
            if (header && pin) header.textContent = `Editing pin: ${fmtTime(pin.t)} — ${pinLabelJS(pin)}`;
            const activeEl = document.activeElement;
            if (!(activeEl && (activeEl.classList?.contains("framing-zoom") || activeEl.tagName === "INPUT"))) refreshEditPanel(record);
          }
          const addBtn = document.querySelector("#review-view .framing-add-pin");
          if (addBtn) {
            const label = `Change frame here — at ${fmtTime(t)}`;
            if (addBtn.textContent !== label) addBtn.textContent = label;
          }
        });
      }
    }
    if (groupName === "trim") {
      const bounds = currentEditsFor(record);
      const sourceDuration = Number(record.source?.duration);
      const maximum = Number.isFinite(sourceDuration) && sourceDuration > 0 ? sourceDuration : Math.max(Number(record.end) || 0, Number(bounds.end) || 0);
      const option = node(body, "section", undefined, "edit-option trim-editor");
      node(option, "p", `Choose the start and end of this clip. Current length: ${fmtTime(Math.max(0, Number(bounds.end) - Number(bounds.start)))}.`, "trim-summary");
      const setTrim = (key, value, source) => {
        const number = Number(value);
        const other = Number(currentEditsFor(record)[key === "start" ? "end" : "start"]);
        const valid = Number.isFinite(number) && number >= 0 && number <= maximum && (key === "start" ? number < other : number > other);
        if (!valid) {
          if (state.editSession?.recordKey === reviewKey(record)) state.editSession.trimError = "Start must be before end and stay inside the source video.";
          const error = body.querySelector(".trim-error"); if (error) error.textContent = state.editSession.trimError;
          return;
        }
        state.editSession.edits[key] = number;
        if (source === "range") body.querySelector(`.trim-time-${key}`).value = number.toFixed(2);
        else body.querySelector(`.trim-range-${key}`).value = String(number);
        state.editSession.trimError = "";
        const error = body.querySelector(".trim-error"); if (error) error.textContent = "";
        const summary = body.querySelector(".trim-summary"); if (summary) summary.textContent = `Choose the start and end of this clip. Current length: ${fmtTime(Math.max(0, state.editSession.edits.end - state.editSession.edits.start))}.`;
        const seek = document.querySelector("#review-view .edit-seek"); if (seek) seek.max = String(Math.max(1, state.editSession.edits.end - state.editSession.edits.start));
        video.currentTime = number;
      };
      [["start", "Start", Number(bounds.start)], ["end", "End", Number(bounds.end)]].forEach(([key, label, value]) => {
        const row = node(option, "label", undefined, "trim-row"); node(row, "span", label);
        const range = input(row, "range", value); range.className = `trim-range-${key}`; range.min = 0; range.max = maximum; range.step = .01; range.setAttribute("aria-label", `${label} time`);
        const time = input(row, "number", value.toFixed(2)); time.className = `trim-time-${key}`; time.min = 0; time.max = maximum; time.step = .01; time.setAttribute("aria-label", `${label} time in seconds`);
        range.addEventListener("input", () => setTrim(key, range.value, "range")); time.addEventListener("change", () => setTrim(key, time.value, "time"));
      });
      node(option, "p", state.editSession?.trimError || "", "trim-error");
      return;
    }
    if (groupName === "framing") {
      const framing = state.editSession?.recordKey === reviewKey(record) ? state.editSession.framing : null;
      const shell = video?.closest(".video-shell");
      if (shell) {
        shell.classList.add("framing-active");
        if (!shell.dataset.pinDrag) {
          shell.dataset.pinDrag = "1";
          let drag = null;
          shell.addEventListener("pointerdown", event => {
            if (event.button !== 0 || state.editGroup !== "framing" || event.target.closest("button")) return;
            const current = recordForSelection(state.selectedJobId, state.selectedId);
            const session = state.editSession;
            if (!current || !session?.framing || session.recordKey !== reviewKey(current)) return;
            const currentVideo = shell.querySelector("video");
            const {t} = clipTimeOf(currentVideo, current);
            const pins = session.framing.pins;
            const activePin = pins[activePinIndex(pins, t)];
            const rect = pinRectJS(current, activePin, session.framing.shape);
            const box = shell.getBoundingClientRect();
            const winH = session.framing.shape === "9:16" ? FRAMING_FEED_WINDOW.height : 1;
            drag = {record: current, pin: activePin, startX: event.clientX, startY: event.clientY, moveX: activePin.move_x, moveY: activePin.move_y, kx: box.width / rect.w, ky: box.height * winH / rect.h, moved: false};
          });
          shell.addEventListener("pointermove", event => {
            if (!drag) return;
            const dx = event.clientX - drag.startX, dy = event.clientY - drag.startY;
            if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
            if (!drag.moved) return;
            const sourceW = Number(drag.record.source?.width) || 1920;
            const sourceH = Number(drag.record.source?.height) || 1080;
            drag.pin.move_x = Math.max(-1, Math.min(1, drag.moveX - (dx / drag.kx) / (sourceW * .25)));
            drag.pin.move_y = Math.max(-1, Math.min(1, drag.moveY - (dy / drag.ky) / (sourceH * .25)));
            drag.pin.preset = "custom";
            applyPinPreview(drag.record, shell.querySelector("video"));
          });
          const endDrag = () => { if (!drag) return; const done = drag; drag = null; if (done.moved) { scheduleFramingSave(done.record, true); refreshEditPanel(done.record); } };
          shell.addEventListener("pointerup", endDrag);
          shell.addEventListener("pointercancel", endDrag);
        }
      }
      if (!framing) { node(body, "p", "Open this clip to edit its framing.", "help"); return; }
      const bounds = currentEditsFor(record);
      const duration = Math.max(0, Number(bounds.end) - Number(bounds.start));
      const {t: clipNow} = clipTimeOf(video, record);
      const pins = framing.pins;
      const activeIndex = activePinIndex(pins, clipNow);
      const pin = pins[activeIndex];
      framing.activeT = pin.t;
      const option = node(body, "section", undefined, "edit-option framing-editor");
      node(option, "h3", `Editing pin: ${fmtTime(pin.t)} — ${pinLabelJS(pin)}`, "framing-pin-header");
      node(option, "p", "", "framing-save-status").setAttribute("role", "status");
      const addButton = button(option, `Change frame here — at ${fmtTime(clipNow)}`, () => {
        const now = clipTimeOf(video, record).t;
        const existing = pins.find(item => Math.abs(Number(item.t) - now) < .05);
        if (existing) { showMessage("info", "Pin already here", `You are editing the pin at ${fmtTime(existing.t)}. Drag the picture, zoom, or pick a preset.`); return; }
        const source = pins[activePinIndex(pins, now)] || pin;
        const copy = {...source, t: Math.round(now * 1000) / 1000};
        framing.pins = [...pins, copy].sort((a, b) => a.t - b.t);
        scheduleFramingSave(record, true);
        refreshEditPanel(record);
      }, "framing-add-pin button-primary button-large");
      const strip = node(option, "div", undefined, "framing-pin-strip");
      pins.forEach(each => {
        const dot = button(strip, undefined, () => {}, `framing-pin-dot${each === pin ? " active" : ""}`);
        dot.style.left = `${duration > 0 ? Math.min(100, Math.max(0, Number(each.t) / duration * 100)) : 0}%`;
        dot.title = `${fmtTime(each.t)} — ${pinLabelJS(each)}`;
        dot.setAttribute("aria-label", `Pin at ${fmtTime(each.t)} — ${pinLabelJS(each)}`);
        let dotDrag = null;
        dot.addEventListener("pointerdown", event => {
          event.preventDefault();
          dotDrag = {startX: event.clientX, startT: Number(each.t), moved: false};
          dot.setPointerCapture?.(event.pointerId);
        });
        dot.addEventListener("pointermove", event => {
          if (!dotDrag || Number(each.t) === 0) return;
          const width = strip.getBoundingClientRect().width || 1;
          const dt = (event.clientX - dotDrag.startX) / width * duration;
          if (Math.abs(event.clientX - dotDrag.startX) > 4) dotDrag.moved = true;
          if (!dotDrag.moved) return;
          const index = framing.pins.indexOf(each);
          const low = index > 0 ? Number(framing.pins[index - 1].t) + .05 : 0;
          const high = index < framing.pins.length - 1 ? Number(framing.pins[index + 1].t) - .05 : duration;
          each.t = Math.round(Math.min(high, Math.max(low, dotDrag.startT + dt)) * 1000) / 1000;
          dot.style.left = `${duration > 0 ? each.t / duration * 100 : 0}%`;
          video.currentTime = mediaOffsetFor(video, record) + Number(each.t);
        });
        dot.addEventListener("pointerup", () => {
          if (!dotDrag) return;
          const wasDrag = dotDrag.moved; dotDrag = null;
          video.currentTime = mediaOffsetFor(video, record) + Number(each.t);
          if (wasDrag) { scheduleFramingSave(record, true); }
          refreshEditPanel(record);
        });
      });
      node(option, "p", "Tap a pin to edit it. Drag a pin sideways to move when it happens.", "help");
      const pinActions = node(option, "div", undefined, "choice-row");
      const nudge = (delta) => {
        const index = framing.pins.indexOf(pin);
        const low = index > 0 ? Number(framing.pins[index - 1].t) + .05 : 0;
        const high = index < framing.pins.length - 1 ? Number(framing.pins[index + 1].t) - .05 : duration;
        pin.t = Math.round(Math.min(high, Math.max(low, Number(pin.t) + delta)) * 1000) / 1000;
        video.currentTime = mediaOffsetFor(video, record) + Number(pin.t);
        scheduleFramingSave(record, true);
        refreshEditPanel(record);
      };
      const backBtn = button(pinActions, "−1 sec", () => nudge(-1), "choice framing-nudge-back");
      const fwdBtn = button(pinActions, "+1 sec", () => nudge(1), "choice framing-nudge-fwd");
      backBtn.disabled = fwdBtn.disabled = Number(pin.t) === 0;
      if (Number(pin.t) !== 0) {
        button(pinActions, "Delete pin", () => {
          framing.pins = framing.pins.filter(item => item !== pin);
          scheduleFramingSave(record, true);
          refreshEditPanel(record);
        }, "choice framing-delete-pin");
      }
      const zoomSection = node(body, "section", undefined, "edit-option");
      node(zoomSection, "h3", "Zoom");
      node(zoomSection, "p", "100% shows the whole frame. 250% is close on a face.", "help");
      const zoomRow = node(zoomSection, "div", undefined, "framing-zoom-row");
      const zoomRange = input(zoomRow, "range", Math.round(Number(pin.zoom) * 100));
      zoomRange.className = "framing-zoom"; zoomRange.min = 100; zoomRange.max = 250; zoomRange.step = 1; zoomRange.setAttribute("aria-label", "Zoom");
      zoomRange.value = String(Math.round(Number(pin.zoom) * 100));
      const zoomValue = node(zoomRow, "span", `${Math.round(Number(pin.zoom) * 100)}%`, "framing-zoom-value");
      zoomRange.addEventListener("input", () => {
        pin.zoom = Number(zoomRange.value) / 100;
        if (pin.preset !== "custom") pin.preset = "custom";
        zoomValue.textContent = `${zoomRange.value}%`;
        applyPinPreview(record, video);
        scheduleFramingSave(record);
      });
      zoomRange.addEventListener("change", () => refreshEditPanel(record));
      const presetSection = node(body, "section", undefined, "edit-option");
      node(presetSection, "h3", "Quick looks");
      node(presetSection, "p", "One tap sets the frame. Drag or zoom after to fine-tune.", "help");
      const presetRow = node(presetSection, "div", undefined, "choice-row");
      const applyPresetValues = (values, presetName) => {
        pin.zoom = values.zoom; pin.move_x = values.move_x; pin.move_y = values.move_y; pin.preset = presetName;
        applyPinPreview(record, video);
        scheduleFramingSave(record, true);
        refreshEditPanel(record);
      };
      [["auto", "Auto"], ["wide", "Wide"]].forEach(([name, label]) => {
        button(presetRow, label, () => applyPresetValues({zoom: 1, move_x: 0, move_y: 0}, name), `choice framing-preset${pin.preset === name ? " active" : ""}`);
      });
      [["a", "Person A"], ["b", "Person B"], ["both", "Both"]].forEach(([name, label]) => {
        button(presetRow, label, async element => {
          element.disabled = true;
          try {
            const result = await get(`/api/candidates/${encodeURIComponent(record.job_id)}/${encodeURIComponent(record.id)}/framing-presets?t=${encodeURIComponent(pin.t)}`);
            if (result?.available && result[name]) applyPresetValues(result[name], name);
            else showMessage("info", "No face here yet", "Person looks need this video's face analysis. Export the clip once, then try again.");
          } catch { showMessage("error", "Preset failed", "Could not load the person look. Try again."); }
          element.disabled = false;
        }, `choice framing-preset${pin.preset === name ? " active" : ""}`);
      });
      const shapeSection = node(body, "section", undefined, "edit-option");
      node(shapeSection, "h3", "Clip shape");
      const shapeRow = node(shapeSection, "div", undefined, "choice-row");
      [["9:16", "9:16 Vertical"], ["1:1", "1:1 Square"], ["16:9", "16:9 Wide"]].forEach(([name, label]) => {
        button(shapeRow, label, () => {
          framing.shape = name;
          applyPinPreview(record, video);
          scheduleFramingSave(record, true);
          refreshEditPanel(record);
        }, `choice framing-shape${framing.shape === name ? " active" : ""}`);
      });
      const resetSection = node(body, "section", undefined, "edit-option");
      button(resetSection, "Reset this pin", () => {
        pin.zoom = 1; pin.move_x = 0; pin.move_y = 0; pin.preset = "auto";
        applyPinPreview(record, video);
        scheduleFramingSave(record, true);
        refreshEditPanel(record);
      }, "button-secondary framing-reset");
      node(resetSection, "p", "Reset puts this pin back to the default frame. It does not delete any pin.", "help");
      node(body, "p", "Drag the picture inside the frame to move it. Pin changes save automatically.", "help");
      applyPinPreview(record, video);
      setFramingStatus(record);
      return;
    }
    if (groupName === "captions") {
      buildCaptionsGroup(body, record, video, controls);
      return;
    }
    const option = node(body, "section", undefined, "edit-option");
    node(option, "h3", "Pick how the two people should look");
    node(option, "p", "Choose a starting look while keeping the selected video visible.");
    const layouts = node(option, "div", undefined, "layout-grid");
    [["one", "One person", "Only the speaker", "one"], ["blended", "Both blended", "A soft join", ""], ["stacked", "Both stacked", "One above the other", "stack"], ["duo", "Duo style", "Switches by voice", "duo"]].forEach(([value, label, note, icon]) => {
      const choice = button(layouts, undefined, () => {
        state.speakerLayoutHint = value;
        window.SpeakerFrame?.open(record, {post, node, button, input, select, withToken, showMessage, addActivity, actionButton, refresh, renderReview, layoutHint: value});
      }, `layout-choice${state.speakerLayoutHint === value ? " active" : ""}`);
      node(choice, "i", undefined, `layout-icon ${icon}`); node(choice, "span", label); node(choice, "small", note);
    });
    button(body, "Open Speaker Frame editor", () => window.SpeakerFrame?.open(record, {post, node, button, input, select, withToken, showMessage, addActivity, actionButton, refresh, renderReview, layoutHint: state.speakerLayoutHint || "auto"}), "button-primary button-large");
    node(body, "p", state.editAdvanced ? "Advanced Speaker Frame settings remain available in its editor." : "Simple mode keeps the main choices visible first.", "edit-footer-note");
  };

  const renderEditPanel = (parent, record, video, overlay) => {
    const panel = node(parent, "aside", undefined, "edit-panel");
    startCaptionPreview(record, video);
    panel.dataset.editKey = reviewKey(record);
    const heading = node(panel, "div", undefined, "edit-heading");
    const headingText = node(heading, "div", undefined, "edit-heading-text");
    node(headingText, "h2", "Edit while watching");
    node(headingText, "p", sourceTitleFor(record), "edit-source-title");
    const headingActions = node(heading, "div", undefined, "edit-heading-actions");
    button(headingActions, "Save & Done", () => saveEditAndDone(record), "edit-save-button done-button");
    button(headingActions, "Cancel Edit", () => requestCancelEdit(record), "edit-cancel-button");
    const headline = node(panel, "label", undefined, "edit-headline-field");
    node(headline, "span", "Headline");
    const headlineInput = input(headline, "text", currentHeadlineFor(record));
    headlineInput.maxLength = 78; headlineInput.setAttribute("aria-label", "Headline");
    headlineInput.addEventListener("input", () => { if (state.editSession?.recordKey === reviewKey(record)) state.editSession.headline = headlineInput.value; applyHeadlineOverlay(video.closest(".video-shell"), record, headlineInput.value); });
    node(panel, "p", "This title is saved with the selected clip.", "edit-clip-title");
    const savedInfo = state.editSession?.recordKey === reviewKey(record) ? state.editSession : null;
    const savedLineText = !savedInfo || savedInfo.savedLoadState === "loading" ? "Loading the saved headline from the server…" : savedInfo.savedLoadState === "error" ? `Could not load the saved headline from the server. ${savedInfo.savedLoadError || ""} What you see may be out of date.` : savedHeadlineText(savedInfo.savedHeadline);
    node(panel, "p", savedLineText, "edit-saved-headline");
    if (savedInfo && savedInfo.savedLoadState === "loading") headlineInput.disabled = true;
    const mode = node(panel, "div", undefined, "edit-mode");
    node(mode, "span", "Show", "edit-mode-label");
    [false, true].forEach(advanced => {
      const modeButton = button(mode, advanced ? "Advanced" : "Simple", () => {
        state.editAdvanced = advanced;
        try { localStorage.setItem("debate-clipper-edit-mode", advanced ? "advanced" : "simple"); } catch {}
        refreshEditPanel(record);
      }, `edit-mode-button${state.editAdvanced === advanced ? " active" : ""}`);
      modeButton.setAttribute("aria-pressed", String(state.editAdvanced === advanced));
    });
    const status = node(panel, "p", state.editSavePending ? "Saving…" : state.editDiscardConfirm ? "Discard changes that are not saved?" : "", "edit-save-status");
    status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    if (state.editDiscardConfirm) {
      const confirm = node(panel, "div", undefined, "edit-discard-confirm");
      node(confirm, "strong", "Discard changes that are not saved?");
      button(confirm, "Keep editing", () => { state.editDiscardConfirm = false; refreshEditPanel(record); }, "button-secondary");
      button(confirm, "Discard", () => { restoreEditSession(record); applyPreview(video, overlay, controlsFor(record)); closeReviewEdit(record); }, "button-secondary");
    }
    const controls = controlsFor(record);
    const groups = node(panel, "div", undefined, "edit-accordion");
    const groupData = [
      ["speaker", "Speaker Frame", "Choose how the speakers appear."],
      ["trim", "Trim", "Set where the clip starts and ends."],
      ["framing", "Framing", "Choose the crop and camera feel."],
      ["captions", "Captions", "Choose the caption look."],
    ];
    groupData.forEach(([groupName, label, description]) => {
      const group = node(groups, "section", undefined, `edit-accordion-group${state.editGroup === groupName ? " open" : ""}`);
      const groupId = `edit-group-${record.id}-${groupName}`.replace(/[^A-Za-z0-9_-]/g, "-");
      const trigger = button(group, undefined, () => { state.editGroup = groupName; state.editDiscardConfirm = false; refreshEditPanel(record, {focusGroup: groupName}); }, "edit-accordion-trigger");
      trigger.setAttribute("aria-expanded", String(state.editGroup === groupName)); trigger.setAttribute("aria-controls", groupId);
      node(trigger, "span", label); node(trigger, "small", description);
      const body = node(group, "div", undefined, "edit-accordion-body"); body.id = groupId; body.hidden = state.editGroup !== groupName;
      if (state.editGroup === groupName) renderEditGroupContent(body, groupName, record, video, overlay, controls);
    });
    const footer = node(panel, "div", undefined, "edit-footer");
    node(footer, "p", "Save & Done keeps your changes with this clip.", "edit-footer-note");
    button(footer, "Save & Done", () => saveEditAndDone(record), "edit-save-button button-primary button-large");
    button(footer, "Cancel Edit", () => requestCancelEdit(record), "edit-cancel-button button-secondary");
    if (savedInfo && savedInfo.savedLoadState === "loading") panel.querySelectorAll(".edit-save-button").forEach(saveButton => { saveButton.disabled = true; });
    return panel;
  };

  const renderReview = (records = state.candidates) => {
    stopVideos();
    const visibleRecords = records.filter(record => !state.jobs.some(job => job.job_id === record.job_id && job.is_test));
    const view = document.getElementById("review-view");
    clear(view);
    addHint(view, "review", "Choose a clip, watch it, then Approve, Reject, Edit, or Export.");
    const heading = node(view, "div", undefined, "review-heading");
    node(heading, "p", "Step 3 of 4", "eyebrow");
    node(heading, "h1", visibleRecords.length ? "Review your clips." : "No clips are ready yet.");
    node(heading, "p", visibleRecords.length ? "Your clips stay grouped by the long video they came from. Only one selected clip loads here." : "Add a video first, then come back when clips are ready.");
    if (!visibleRecords.length) { button(heading, "Go to Add video", renderHome, "button-primary"); showView("review"); return; }
    const groups = new Map();
    visibleRecords.forEach(item => {
      const groupId = sourceGroupFor(item);
      if (!groups.has(groupId)) groups.set(groupId, {id: groupId, title: sourceTitleFor(item), records: []});
      groups.get(groupId).records.push(item);
    });
    if (!state.reviewGroupId || !groups.has(state.reviewGroupId)) state.reviewGroupId = groups.keys().next().value;
    const currentGroup = groups.get(state.reviewGroupId) || groups.values().next().value;
    let record = null;
    let selectionError = "";
    if (state.selectedId) {
      record = recordForSelection(state.selectedJobId, state.selectedId, currentGroup.records);
      if (!record) {
        const sameId = currentGroup.records.filter(item => item.id === state.selectedId);
        selectionError = sameId.length > 1 ? "That clip appears in more than one job for this video, and we could not tell which one you picked. Nothing was opened. Pick the clip again." : "That clip could not be found in this video's clips. Pick a clip from the list.";
      }
    } else {
      record = currentGroup.records[0] || null;
    }
    if (record) { state.selectedId = record.id; state.selectedJobId = record.job_id; }
    const layout = node(view, "div", undefined, `review-layout${state.editing ? " editing" : ""}`);
    const sidebar = node(layout, "aside", undefined, "clip-sidebar");
    node(sidebar, "h2", "Your videos");
    const list = node(sidebar, "div", undefined, "clip-list");
    groups.forEach(group => {
      const groupSection = node(list, "section", undefined, `source-group${group.id === currentGroup.id ? " selected-group" : ""}`);
      groupSection.dataset.groupId = group.id;
      node(groupSection, "h3", group.title);
      node(groupSection, "p", groupProgressFor(group.records), "group-progress");
      const runs = new Map();
      group.records.forEach(item => { const runId = runFor(item); if (!runs.has(runId)) runs.set(runId, []); runs.get(runId).push(item); });
      runs.forEach((runRecords, runId) => {
        const run = node(groupSection, "div", undefined, "source-run");
        node(run, "h4", `Clips found · ${fmtDate(runRecords[0].source?.run_created_at)} · ${runRecords.length}`);
        runRecords.forEach(item => {
          const row = button(run, undefined, () => { state.reviewGroupId = group.id; state.selectedId = item.id; state.selectedJobId = item.job_id; state.editing = false; state.editSession = null; state.editDiscardConfirm = false; state.editSavePending = false; renderReview(visibleRecords); }, `clip-row${record && item.id === record.id && item.job_id === record.job_id ? " selected" : ""}`);
          row.dataset.reviewKey = reviewKey(item);
          const thumb = node(row, "span", undefined, "clip-thumb");
          if (item.export?.cover) { const image = node(thumb, "img"); image.src = withToken(item.export.cover); image.alt = ""; }
          const text = node(row, "span");
          node(text, "strong", titleFor(item));
          const meta = node(text, "small", `${fmtTime(Number(item.end) - Number(item.start))} · ${fmtTime(item.start)}–${fmtTime(item.end)}`);
          node(meta, "span", scoreWord(item.score), `rating ${scoreClass(item.score)}`);
          const status = stateFor(item);
          const badge = node(text, "span", status, `status-badge status-${stateClass(status)}`);
          badge.hidden = status === "Not reviewed";
        });
      });
    });
    if (selectionError) {
      const notice = node(layout, "p", selectionError, "message-error");
      notice.setAttribute("role", "alert");
      showView("review");
      return;
    }
    const stage = node(layout, "main", undefined, "review-stage");
    const shell = node(stage, "div", undefined, "video-shell");
    const video = node(shell, "video");
    const overlay = null;
    configureVideo(video, record, state.editing);
    applyPreview(video, overlay, controlsFor(record));
    applyHeadlineOverlay(shell, record);
    node(stage, "p", "Preview of the selected moment", "preview-label");
    node(stage, "span", record.decision?.speaker_frame?.enabled ? "Framing: Speaker Frame" : "Framing: Auto", "framing-badge");
    if (state.editing) renderEditPlayback(stage, video, record);
    {
      const actions = node(layout, "aside", undefined, "review-actions");
      actions.dataset.reviewKey = reviewKey(record);
      const approve = button(actions, "Approve", element => saveAction(element, record, "approve"), "approve review-action");
      const reject = button(actions, "Reject", element => saveAction(element, record, "reject"), "reject review-action");
      const edit = button(actions, "Edit", () => toggleReviewEdit(record, true), "edit review-action");
      const exportButton = button(actions, "Export", element => exportClip(element, record), "export review-action");
      [approve, reject, edit, exportButton].forEach((element, index) => { element.dataset.action = ["approve", "reject", "edit", "export"][index]; });
      const feedback = node(actions, "p", "", "review-feedback");
      feedback.setAttribute("role", "status"); feedback.setAttribute("aria-live", "polite");
      const progressLink = node(actions, "a", "View export progress", "link-button view-export");
      progressLink.href = "#";
      progressLink.addEventListener("click", event => event.preventDefault());
      progressLink.hidden = true;
      scoreDetails(actions, record);
      approve.setAttribute("aria-label", `Approve ${titleFor(record)}`);
    }
    if (state.editing) renderEditPanel(layout, record, video, overlay);
    syncReviewState();
    showView("review");
  };
  const saveAction = async (element, record, action) => {
    const key = reviewKey(record);
    if (state.reviewPending[key]) return;
    state.reviewPending[key] = action;
    state.reviewFeedback[key] = {text: action === "approve" ? "Saving approval…" : "Saving rejection…"};
    syncReviewState();
    try {
      const data = await saveDecision(record, action);
      storeDecision(record, data);
      addActivity(`${action === "approve" ? "Approved" : "Rejected"} a clip`);
      state.reviewFeedback[key] = {text: action === "approve" ? "Clip approved" : "Clip rejected"};
      showMessage("success", action === "approve" ? "Clip approved" : "Clip rejected", action === "approve" ? "You can export it now." : "It will not be exported.");
    } catch (error) {
      addActivity("Could not save clip choice", "error");
      state.reviewFeedback[key] = {kind: "error", text: `Could not ${action === "approve" ? "approve" : "reject"} this clip. ${error.message} Try again.`};
      showMessage("error", "Could not save this choice", error.message);
    } finally { delete state.reviewPending[key]; syncReviewState(); }
  };
  const exportClip = async (element, record) => {
    const key = reviewKey(record);
    if (state.reviewPending[key]) return;
    const buttonState = exportButtonFor(record);
    if (buttonState.kind === "exported") { state.lastExport = buttonState.exported; renderExportDone(buttonState.exported); return; }
    if (buttonState.disabled) { if (buttonState.attempt) openReviewExport(buttonState.attempt); return; }
    state.reviewPending[key] = "export";
    state.reviewFeedback[key] = {text: "Saving approval and settings before export…"};
    syncReviewState();
    let attempt;
    try {
      storeDecision(record, await saveDecision(record, "approve"));
      const exportId = `export_${crypto.randomUUID().replaceAll("-", "")}`;
      attempt = {export_id: exportId, job_id: record.job_id, candidate_id: record.id, title: titleFor(record), source_title: sourceTitleFor(record), edit_revision: record.edit_revision, status: "exporting", stage: "Preparing the video", started_at: new Date().toISOString()};
      rememberAttempt(attempt);
      state.reviewFeedback[key] = {text: ""};
      // Give the pressed button a painted working state before the forward handoff.
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      openReviewExport(attempt);
      const result = await post("/api/render", {job_id: record.job_id, candidate_id: record.id, variants: 1, export_id: exportId});
      attempt = result.attempt || {...attempt, status: result.export ? "exported" : "failed", export: result.export, reason: "The export did not produce a verified file. Try again."};
      rememberAttempt(attempt);
      await refresh();
      const updated = state.candidates.find(item => reviewKey(item) === key) || record;
      if (attempt.status === "exported" && attempt.export) {
        updated.export = attempt.export; state.lastExport = attempt.export;
        state.reviewFeedback[key] = {text: "Exported ✓"};
        addActivity("Export finished");
      } else if (attempt.status !== "exporting") {
        state.reviewFeedback[key] = {kind: "error", text: attempt.reason || "Export failed. Try again."};
        addActivity("Export failed", "error");
      }
      if (state.view === "export" && state.exportFocusId === attempt.export_id) renderReviewExport(attempt);
    } catch (error) {
      if (!attempt) {
        state.reviewFeedback[key] = {kind: "error", text: `Could not save before export. ${error.message} Try again.`};
      } else if (error.status === 409) {
        state.reviewExports = state.reviewExports.filter(item => item.export_id !== attempt.export_id);
        rememberAttempt(error.attempt);
        state.reviewFeedback[key] = {text: error.message};
        if (state.view === "export") {
          if (error.attempt) openReviewExport(error.attempt);
          else { renderReview(state.candidates); showMessage("warning", "Another export is already running", "Wait for the running export to finish, then try again."); }
        }
      } else {
        // A disconnected browser cannot decide whether the server is still rendering.
        if (!error.status) { setConnection(false); state.reviewFeedback[key] = {text: "Checking the export status. Reconnect to Studio to see the result."}; }
        else {
          attempt = {...attempt, status: "failed", reason: error.message}; rememberAttempt(attempt);
          state.reviewFeedback[key] = {kind: "error", text: `Export failed. ${error.message} Try again.`};
          if (state.view === "export" && state.exportFocusId === attempt.export_id) renderReviewExport(attempt);
        }
      }
    } finally { delete state.reviewPending[key]; syncReviewState(); }
  };

  const openReviewExport = attempt => { state.exportFocusId = attempt.export_id; renderReviewExport(attempt); };
  const renderReviewExport = attempt => {
    if (attempt.status === "exported" && attempt.export) { state.lastExport = attempt.export; renderExportDone(attempt.export); return; }
    stopVideos();
    const view = document.getElementById("export-view"); clear(view);
    const panel = node(view, "section", undefined, "export-panel narrow review-export-handoff");
    panel.dataset.exportId = attempt.export_id;
    node(panel, "p", "Step 4 of 4", "eyebrow");
    node(panel, "h1", attempt.status === "exporting" ? "Making your video" : attempt.status === "not_finished" ? "Not finished" : "Export failed");
    node(panel, "h2", attempt.title);
    node(panel, "p", attempt.source_title, "sub");
    if (attempt.status === "exporting") {
      node(panel, "p", "Exporting…", "export-status");
      node(panel, "strong", attempt.stage || "Preparing the video", "export-stage");
      const track = node(panel, "div", undefined, "progress-track"); node(track, "span", undefined, "progress-fill indeterminate");
      node(panel, "p", `Time so far: ${formatElapsed(Date.now() - Date.parse(attempt.started_at))}`, "export-elapsed");
    } else {
      node(panel, "p", attempt.reason || "The export could not finish. Try again.", "find-error");
      button(panel, "Try again", element => {
        const record = state.candidates.find(item => item.job_id === attempt.job_id && item.id === attempt.candidate_id);
        if (record) exportClip(element, record);
      }, "button-primary");
    }
    button(panel, "Back to Review", () => renderReview(state.candidates), "link-button export-back");
    showView("export");
  };

  const copyPath = async exportData => {
    try { await navigator.clipboard.writeText(exportData.clip); showMessage("success", "File path copied", "The file path is on your clipboard."); }
    catch { showMessage("warning", "Copy did not work", exportData.clip); }
  };
  const openFolder = async exportData => {
    try {
      const result = await post(`/api/exports/${exportData.key}/open-folder`, {});
      showMessage(result.status === "opened" ? "success" : "warning", result.status === "opened" ? "Folder opened" : "Open the folder yourself", result.path);
    } catch (error) { showMessage("error", "Could not open the folder", error.message); }
  };
  const playExport = exportData => {
    const url = withToken(exportData.file_url);
    const player = window.open(url, "_blank", "noopener");
    if (!player) showMessage("warning", "The clip could not open", "Allow pop-ups for Debate Clipper, then press Play again.");
  };
  const renderExportDone = exportData => {
    stopVideos();
    const view = document.getElementById("export-view");
    clear(view);
    addHint(view, "export", "Your file is saved on this computer. Nothing is uploaded automatically.");
    const panel = node(view, "section", undefined, "export-panel narrow");
    node(panel, "p", "Step 4 of 4", "eyebrow");
    node(panel, "h1", "Exported ✓");
    const ready = node(panel, "div", "Your clip is ready", "ready");
    ready.setAttribute("role", "status");
    node(panel, "div", exportData.clip_name || "Your video file", "file-name");
    const actions = node(panel, "div", undefined, "export-actions");
    button(actions, "Play", () => playExport(exportData));
    button(actions, "Open folder", () => openFolder(exportData));
    button(actions, "Copy file path", () => copyPath(exportData));
    button(panel, "Back to my clips", () => renderReview(state.candidates), "link-button export-back");
    showView("export");
  };
  const renderExport = () => {
    const attempt = state.reviewExports.find(item => item.export_id === state.exportFocusId) || runningExport();
    if (attempt) { openReviewExport(attempt); return; }
    if (state.lastExport) { renderExportDone(state.lastExport); return; }
    const view = document.getElementById("export-view");
    clear(view);
    const panel = node(view, "section", undefined, "export-panel narrow");
    node(panel, "p", "Step 4 of 4", "eyebrow");
    node(panel, "h1", "Your finished videos");
    node(panel, "p", "Approve a clip in Review, then press Export.", "sub");
    button(panel, "Back to my clips", () => renderReview(state.candidates), "button-primary button-large");
    showView("export");
  };
  const renderExports = () => {
    stopVideos();
    const view = document.getElementById("exports-view");
    clear(view);
    const panel = node(view, "section", undefined, "exports-panel");
    node(panel, "p", "My exports", "eyebrow");
    node(panel, "h1", "Your finished videos");
    node(panel, "p", "Everything you have made, newest first. These are local files.", "sub");
    if (!state.exports.length) node(panel, "p", "No finished videos yet. Approve a clip and press Export.", "empty");
    const list = node(panel, "div", undefined, "exports-list");
    state.exports.forEach(item => {
      const row = node(list, "article", undefined, "export-row");
      if (item.cover) { const image = node(row, "img"); image.src = withToken(item.cover); image.alt = ""; }
      else node(row, "div", "", "export-placeholder");
      const info = node(row, "div");
      node(info, "h2", item.title || "Finished clip");
      node(info, "p", `${item.source_title || "Debate video"} · ${fmtTime(item.start)} to ${fmtTime(item.end)}`);
      node(info, "p", `${fmtDate(item.date)} · ${fmtSize(item.size)}`);
      const actions = node(info, "div", undefined, "primary-actions");
      button(actions, "Play", () => playExport(item), "button-primary");
      button(actions, "Open folder", () => openFolder(item), "button-secondary");
      button(actions, "Copy file path", () => copyPath(item), "button-secondary");
    });
    button(panel, "Add another video", renderHome, "link-button export-back");
    renderActivity(view);
    showView("exports");
  };
  const showHelp = () => showMessage("success", "How Debate Clipper works", "1. Add a video. 2. Wait while clips are found. 3. Watch and choose a clip. 4. Export when it looks right.");

  document.addEventListener("keydown", event => {
    if (!state.editing || event.code !== "Space" || event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target;
    if (target instanceof HTMLElement && (target.matches("input, textarea, select, button, [contenteditable='true']") || target.isContentEditable)) return;
    const video = document.querySelector("#review-view .review-layout.editing video");
    if (!video) return;
    event.preventDefault();
    if (video.paused) video.play().catch(() => {}); else video.pause();
  });

  document.querySelectorAll(".step").forEach(step => step.addEventListener("click", () => {
    const view = step.dataset.view;
    if (view === "home") renderHome();
    else if (view === "find") state.activeJob ? refreshActiveJob() : renderFind();
    else if (view === "review") renderReview(state.candidates);
    else renderExport();
  }));
  document.getElementById("my-exports")?.addEventListener("click", renderExports);
  document.getElementById("help-button")?.addEventListener("click", showHelp);
  setInterval(() => {
    const panel = document.querySelector("#export-view .review-export-handoff");
    const attempt = state.reviewExports.find(item => item.export_id === panel?.dataset.exportId);
    if (state.view === "export" && attempt?.status === "exporting") {
      panel.querySelector(".export-elapsed").textContent = `Time so far: ${formatElapsed(Date.now() - Date.parse(attempt.started_at))}`;
    }
    if (state.view !== "find" || !state.activeJob) return;
    const value = document.querySelector("#find-view .elapsed-value");
    if (value) value.textContent = formatElapsed(Date.now() - Number(state.activeJob.startedAt || Date.now()));
    document.querySelectorAll("#find-view .find-stages small").forEach(item => {
      if (state.activeJob.stage && item.parentElement?.querySelector("span")?.textContent === stageLabel(state.progress)) item.textContent = `Started ${formatElapsed(Date.now() - Number(state.activeJob.stageStartedAt || Date.now()))} ago`;
    });
  }, 1000);
  setInterval(async () => {
    try {
      await refresh();
      await refreshSystem();
      if (state.view === "home") renderRecent(document.getElementById("home-view"));
      syncReviewState();
      if (state.view === "export" && state.exportFocusId) {
        const attempt = state.reviewExports.find(item => item.export_id === state.exportFocusId);
        const panel = document.querySelector("#export-view .review-export-handoff");
        if (attempt && panel?.dataset.exportId === attempt.export_id) {
          if (attempt.status !== "exporting") renderReviewExport(attempt);
          else panel.querySelector(".export-stage").textContent = attempt.stage || "Preparing the video";
        }
      }
    } catch { setConnection(false); }
  }, 5000);
  (async () => {
    try {
      const data = await refresh();
      if (!restoreActiveJob(data)) renderHome();
      await refreshSystem();
    }
    catch (error) { setConnection(false); showMessage("error", "The Studio could not load", error.message); }
  })();
})();
