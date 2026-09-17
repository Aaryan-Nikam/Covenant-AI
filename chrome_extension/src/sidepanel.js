const DEFAULT_API_BASE_URL = "http://127.0.0.1:8010";

const state = {
  apiBaseUrl: DEFAULT_API_BASE_URL,
  jobs: [],
  selectedJobId: null,
};

const els = {
  apiBaseUrl: document.querySelector("#apiBaseUrl"),
  saveSettings: document.querySelector("#saveSettings"),
  refreshJobs: document.querySelector("#refreshJobs"),
  jobList: document.querySelector("#jobList"),
  jobTotal: document.querySelector("#jobTotal"),
  queuedCount: document.querySelector("#queuedCount"),
  runningCount: document.querySelector("#runningCount"),
  completedCount: document.querySelector("#completedCount"),
  selectedStatus: document.querySelector("#selectedStatus"),
  selectedCampaign: document.querySelector("#selectedCampaign"),
  selectedCsv: document.querySelector("#selectedCsv"),
  selectedColumns: document.querySelector("#selectedColumns"),
  runAgent: document.querySelector("#runAgent"),
  agentStatus: document.querySelector("#agentStatus"),
  toast: document.querySelector("#toast"),
};

init();

async function init() {
  const saved = await chrome.storage.local.get(["apiBaseUrl"]);
  state.apiBaseUrl = saved.apiBaseUrl || DEFAULT_API_BASE_URL;
  els.apiBaseUrl.value = state.apiBaseUrl;
  bindEvents();
  await checkWorkerVersion();
  await loadJobs();
}

function bindEvents() {
  els.saveSettings.addEventListener("click", async () => {
    state.apiBaseUrl = els.apiBaseUrl.value.trim() || DEFAULT_API_BASE_URL;
    await chrome.storage.local.set({ apiBaseUrl: state.apiBaseUrl });
    toast("Settings saved");
    await loadJobs();
  });

  els.refreshJobs.addEventListener("click", () => loadJobs());
  els.runAgent.addEventListener("click", () => runUploadAgent());
}

async function checkWorkerVersion() {
  try {
    const response = await chrome.runtime.sendMessage({ type: "agent.version" });
    if (!response?.ok || response.result?.version !== "0.1.4") {
      toast("Reload extension from chrome://extensions");
    }
  } catch {
    toast("Reload extension from chrome://extensions");
  }
}

async function loadJobs() {
  try {
    const response = await fetch(`${state.apiBaseUrl}/agent-ops/upload-jobs`);
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    state.jobs = data.jobs || [];
    if (!state.selectedJobId && state.jobs[0]) state.selectedJobId = state.jobs[0].id;
    render();
  } catch (error) {
    toast(`Queue load failed: ${error.message}`);
  }
}

function render() {
  const counts = countStatuses(state.jobs);
  els.queuedCount.textContent = counts.queued;
  els.runningCount.textContent = counts.running;
  els.completedCount.textContent = counts.completed;
  els.jobTotal.textContent = `${state.jobs.length} jobs`;

  els.jobList.innerHTML = "";
  for (const job of state.jobs) {
    const item = document.createElement("button");
    item.className = `job ${job.id === state.selectedJobId ? "active" : ""}`;
    item.innerHTML = `
      <div class="job-title">
        <span>${escapeHtml(job.campaign_name || "Unassigned campaign")}</span>
        <span class="badge ${job.status}">${escapeHtml(job.status)}</span>
      </div>
      <div class="job-meta">${job.row_count} rows · ${escapeHtml(job.source_project_name || job.source_project_id || job.source || "webhook")}</div>
    `;
    item.addEventListener("click", () => {
      state.selectedJobId = job.id;
      render();
    });
    els.jobList.appendChild(item);
  }

  const selected = selectedJob();
  els.selectedStatus.textContent = selected?.status || "None";
  els.selectedCampaign.textContent = selected?.campaign_name || "-";
  els.selectedCsv.textContent = selected?.csv_path || "-";
  els.selectedColumns.textContent = selected?.columns?.join(", ") || "-";
}

async function runUploadAgent() {
  const selected = selectedJob();
  if (!selected) return toast("Select a queued job first");
  try {
    els.runAgent.disabled = true;
    els.agentStatus.textContent = "Opening Dripify...";
    const response = await fetch(`${state.apiBaseUrl}/agent-ops/upload-jobs/${selected.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "running" }),
    });
    if (!response.ok) throw new Error(await response.text());
    const setup = await runTool("agent.runUpload", { job: selected });
    await runVisualLoop(selected, setup);
    await loadJobs();
  } catch (error) {
    els.agentStatus.textContent = `Agent failed: ${error.message}`;
    toast(error.message);
  } finally {
    els.runAgent.disabled = false;
  }
}

async function runVisualLoop(job, setup) {
  const history = [];
  let currentSetup = setup;
  for (let step = 0; step < 12; step += 1) {
    els.agentStatus.textContent = `Assessing page, step ${step + 1}...`;
    const decisionResponse = await fetch(`${state.apiBaseUrl}/agent-ops/agent/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        screenshot_data_url: currentSetup.screenshotDataUrl,
        instruction: currentSetup.instruction,
        current_url: currentSetup.url,
        visible_text: currentSetup.visibleText || "",
        campaign_name: job.campaign_name || "",
        clickable_targets: currentSetup.clickableTargets || [],
        step_index: step,
        history,
      }),
    });
    if (!decisionResponse.ok) throw new Error(await decisionResponse.text());
    const decision = await decisionResponse.json();
    const action = decision.action;
    history.push(`${action.action_type}: ${action.reason}`);
    els.agentStatus.textContent = `${action.action_type}: ${action.reason}`;

    if (action.action_type === "complete") {
      await updateJobStatus(job.id, "completed");
      els.agentStatus.textContent = action.message || "Upload completed.";
      toast("Upload completed");
      return;
    }
    if (action.action_type === "escalate") {
      throw new Error(action.message || action.reason || "Agent escalated.");
    }

    await runTool("agent.executeAction", { action });
    await sleep(900);
    currentSetup = await runTool("agent.runUpload", { job });
  }
  throw new Error("Step limit reached before upload completed.");
}

async function updateJobStatus(jobId, status, error = null) {
  const response = await fetch(`${state.apiBaseUrl}/agent-ops/upload-jobs/${jobId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, error }),
  });
  if (!response.ok) throw new Error(await response.text());
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runTool(type, payload = {}) {
  try {
    const response = await chrome.runtime.sendMessage({ type, ...payload });
    if (!response?.ok) throw new Error(response?.error || "Tool failed");
    toast(`${type.replace("agent.", "")} ok`);
    return response.result;
  } catch (error) {
    toast(error.message);
    throw error;
  }
}

function selectedJob() {
  return state.jobs.find((job) => job.id === state.selectedJobId) || null;
}

function countStatuses(jobs) {
  return jobs.reduce(
    (acc, job) => {
      acc[job.status] = (acc[job.status] || 0) + 1;
      return acc;
    },
    { queued: 0, running: 0, completed: 0, failed: 0, cancelled: 0 }
  );
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 2600);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
