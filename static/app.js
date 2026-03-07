/* ── State ─────────────────────────────────────────────────────────────────── */
let currentJobId = null;
let eventSource = null;
let statsInterval = null;

/* ── Init ──────────────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  if (window.__PASSWORD_REQUIRED__) {
    document.getElementById("login-overlay").classList.remove("hidden");
    document.getElementById("logout-btn").classList.remove("hidden");
    bindLogin();
  } else {
    showApp();
  }
});

function showApp() {
  document.getElementById("login-overlay").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  loadStatus();
  bindAll();
}

/* ── Login ─────────────────────────────────────────────────────────────────── */
function bindLogin() {
  const btn = document.getElementById("login-btn");
  const input = document.getElementById("login-password");
  const err = document.getElementById("login-error");

  const attempt = async () => {
    err.classList.add("hidden");
    const res = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: input.value }),
    });
    if (res.ok) { showApp(); }
    else { err.classList.remove("hidden"); input.value = ""; }
  };

  btn.addEventListener("click", attempt);
  input.addEventListener("keydown", e => { if (e.key === "Enter") attempt(); });
}

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/logout", { method: "POST" });
  location.reload();
});

/* ── Bind all interactions ────────────────────────────────────────────────── */
function bindAll() {
  // File uploads
  bindUpload("creds-input", "/api/upload/credentials", "creds-zone", "creds-label", "creds-icon");
  bindUpload("token-input", "/api/upload/token", "token-zone", "token-label", "token-icon");

  // OAuth
  document.getElementById("oauth-btn").addEventListener("click", async () => {
    const res = await fetch("/api/oauth/start");
    if (!res.ok) { alert((await res.json()).error); return; }
    const { url } = await res.json();
    window.open(url, "_blank");
  });

  // Config range label
  const qualityInput = document.getElementById("quality");
  const qualityVal = document.getElementById("quality-val");
  qualityInput.addEventListener("input", () => {
    qualityVal.textContent = qualityInput.value;
  });

  // Save config
  document.getElementById("save-config-btn").addEventListener("click", saveConfig);

  // Run job
  document.getElementById("run-btn").addEventListener("click", startJob);

  // Check if OAuth callback came back
  if (location.search.includes("auth=success")) {
    history.replaceState({}, "", "/");
    loadStatus();
  }
}

/* ── Status ────────────────────────────────────────────────────────────────── */
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    // Auth badge
    const badge = document.getElementById("auth-badge");
    if (data.authenticated) {
      badge.textContent = "Connected";
      badge.className = "badge badge-green";
    } else {
      badge.textContent = "Not connected";
      badge.className = "badge badge-red";
    }

    // Upload zones
    if (data.creds_uploaded) markDone("creds-zone", "creds-label", "creds-icon", "credentials.json ✓");
    if (data.authenticated)   markDone("token-zone",  "token-label",  "token-icon",  "token.json ✓");

    // Populate config
    const cfg = data.config;
    setVal("folder-id",       cfg.folder_id || "");
    setVal("output-folder-id",cfg.output_folder_id || "");
    setVal("quality",         cfg.quality ?? 80);
    setVal("min-size-kb",     cfg.min_size_kb || "");
    setVal("max-width",       cfg.max_width || "");
    setVal("max-height",      cfg.max_height || "");
    document.getElementById("delete-original").checked = !!cfg.delete_original;
    document.getElementById("quality-val").textContent = cfg.quality ?? 80;
  } catch (e) {
    console.error("Status load failed", e);
  }
}

function markDone(zoneId, labelId, iconId, text) {
  document.getElementById(zoneId).classList.add("done");
  document.getElementById(labelId).textContent = text;
  document.getElementById(iconId).textContent = "✅";
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

/* ── File upload ───────────────────────────────────────────────────────────── */
function bindUpload(inputId, endpoint, zoneId, labelId, iconId) {
  document.getElementById(inputId).addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(endpoint, { method: "POST", body: form });
    if (res.ok) {
      markDone(zoneId, labelId, iconId, file.name + " ✓");
      loadStatus();
    } else {
      const err = await res.json();
      alert("Upload failed: " + (err.error || "Unknown error"));
    }
  });
}

/* ── Config ────────────────────────────────────────────────────────────────── */
async function saveConfig() {
  const payload = {
    folder_id:       document.getElementById("folder-id").value.trim(),
    output_folder_id:document.getElementById("output-folder-id").value.trim(),
    quality:         parseInt(document.getElementById("quality").value, 10),
    min_size_kb:     parseInt(document.getElementById("min-size-kb").value || "0", 10),
    max_width:       parseInt(document.getElementById("max-width").value || "0", 10) || null,
    max_height:      parseInt(document.getElementById("max-height").value || "0", 10) || null,
    delete_original: document.getElementById("delete-original").checked,
  };
  const res = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const btn = document.getElementById("save-config-btn");
  if (res.ok) {
    btn.textContent = "Saved ✓";
    setTimeout(() => { btn.textContent = "Save"; }, 2000);
  } else {
    alert("Failed to save config");
  }
}

/* ── Job ───────────────────────────────────────────────────────────────────── */
async function startJob() {
  // Save config first
  await saveConfig();

  const logEl = document.getElementById("log-container");
  const runBtn = document.getElementById("run-btn");

  logEl.innerHTML = "";
  document.getElementById("job-stats").classList.remove("hidden");
  resetStats();
  runBtn.disabled = true;
  runBtn.textContent = "⏳ Running...";

  const res = await fetch("/api/jobs", { method: "POST" });
  if (!res.ok) {
    const err = await res.json();
    appendLog("❌ " + (err.error || "Failed to start job"), "err");
    runBtn.disabled = false;
    runBtn.textContent = "▶ Start Compression";
    return;
  }

  const { job_id } = await res.json();
  currentJobId = job_id;

  // SSE stream
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`/api/jobs/${job_id}/stream`);

  eventSource.onmessage = (e) => {
    const msg = e.data;
    if (msg === "__done__") {
      eventSource.close();
      runBtn.disabled = false;
      runBtn.textContent = "▶ Start Compression";
      pollStats(job_id);
      return;
    }
    if (msg === "__ping__") return;
    appendLog(msg);
    pollStats(job_id);
    logEl.scrollTop = logEl.scrollHeight;
  };

  eventSource.onerror = () => {
    eventSource.close();
    runBtn.disabled = false;
    runBtn.textContent = "▶ Start Compression";
  };
}

function appendLog(msg, type) {
  const logEl = document.getElementById("log-container");
  const line = document.createElement("div");
  line.className = "log-line";
  if (type === "err" || msg.includes("❌") || msg.includes("💥")) line.classList.add("log-line-err");
  else if (msg.includes("✅") || msg.includes("📤")) line.classList.add("log-line-ok");
  else if (msg.includes("📥") || msg.includes("🔍") || msg.includes("⚙️")) line.classList.add("log-line-info");
  line.textContent = msg;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

async function pollStats(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) return;
  const job = await res.json();
  document.getElementById("stat-total").textContent   = job.stats.total   || 0;
  document.getElementById("stat-success").textContent = job.stats.success || 0;
  document.getElementById("stat-failed").textContent  = job.stats.failed  || 0;
}

function resetStats() {
  ["stat-total", "stat-success", "stat-failed"].forEach(id => {
    document.getElementById(id).textContent = "0";
  });
}
