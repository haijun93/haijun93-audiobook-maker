const STRINGS = {
  ko: {
    brandSub: "Korean Audiobook Maker", newJob: "새 오디오북", file: "파일", text: "텍스트",
    chooseFile: "파일 선택", sourceText: "원문", textPlaceholder: "낭독할 한국어 텍스트를 입력하세요",
    provider: "음성 제공자", mode: "구성", modePlain: "원문 낭독", modeMaterial: "자료 중심",
    modeStudy: "학습용", voice: "음성", advanced: "고급 설정", chunkSize: "조각 크기",
    bitrate: "비트레이트", retries: "재시도", model: "모델", showBrowser: "브라우저 창 표시",
    start: "만들기 시작", jobs: "작업", active: "진행 중", ready: "완료", attention: "확인 필요",
    emptyTitle: "대기 중인 작업이 없습니다", emptyBody: "원문과 음성을 선택해 시작하세요.",
    log: "실행 로그", copy: "복사", stop: "중단", download: "다운로드", remove: "삭제",
    queued: "대기 중", running: "생성 중", cancelling: "중단 중", completed: "완료",
    failed: "실패", cancelled: "취소됨", created: "작업을 등록했습니다", copied: "로그를 복사했습니다",
    confirmDelete: "이 작업과 생성 파일을 삭제할까요?",
    apiReady: "API 키 준비됨", apiMissing: "Gemini API 키 필요", browserReady: "Chrome 준비됨",
    browserMissing: "Chrome 또는 로그인 필요", ffmpegMissing: "FFmpeg 확인 필요", selectFile: "파일을 선택하세요",
    enterText: "텍스트를 입력하세요", unknownError: "요청을 처리하지 못했습니다", noLog: "아직 로그가 없습니다.",
    progress: "진행률",
  },
  en: {
    brandSub: "Korean Audiobook Maker", newJob: "New audiobook", file: "File", text: "Text",
    chooseFile: "Choose a file", sourceText: "Source text", textPlaceholder: "Enter Korean text to narrate",
    provider: "Voice provider", mode: "Format", modePlain: "Read source", modeMaterial: "Material only",
    modeStudy: "Study edition", voice: "Voice", advanced: "Advanced", chunkSize: "Chunk size",
    bitrate: "Bitrate", retries: "Retries", model: "Model", showBrowser: "Show browser window",
    start: "Start creating", jobs: "Jobs", active: "Active", ready: "Ready", attention: "Attention",
    emptyTitle: "No jobs yet", emptyBody: "Choose a source and voice to begin.",
    log: "Run log", copy: "Copy", stop: "Stop", download: "Download", remove: "Delete",
    queued: "Queued", running: "Running", cancelling: "Stopping", completed: "Complete",
    failed: "Failed", cancelled: "Cancelled", created: "Job added", copied: "Log copied",
    confirmDelete: "Delete this job and its generated files?",
    apiReady: "API key ready", apiMissing: "Gemini API key required", browserReady: "Chrome ready",
    browserMissing: "Chrome or login required", ffmpegMissing: "Check FFmpeg", selectFile: "Choose a source file",
    enterText: "Enter source text", unknownError: "The request could not be completed", noLog: "No log output yet.",
    progress: "Progress",
  },
};

const VOICES = {
  gemini_api_tts: ["Sulafat", "Kore", "Aoede", "Charon", "Fenrir", "Leda", "Orus", "Puck", "Zephyr"],
  gemini_web: ["account_default"],
  chatgpt_web: ["cove", "fathom", "orbit", "vale", "glimmer", "juniper", "maple", "breeze", "ember"],
};

const state = {
  language: localStorage.getItem("audiobook-language") || "ko",
  system: {}, jobs: [], selectedId: null, logOffset: 0, logText: "", polling: false, submitting: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const t = (key) => STRINGS[state.language][key] || key;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = `toast${error ? " error" : ""}`;
  node.textContent = message;
  $("#toast-region").append(node);
  setTimeout(() => node.remove(), 3600);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
  return data;
}

function applyLanguage() {
  document.documentElement.lang = state.language;
  $$('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });
  $$('[data-i18n-placeholder]').forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
  $$('[data-lang]').forEach((button) => button.classList.toggle("active", button.dataset.lang === state.language));
  renderJobs();
  updateProviderUI();
}

function selectedProvider() {
  return $('input[name="provider"]:checked').value;
}

function updateVoiceOptions() {
  const provider = selectedProvider();
  const voice = $("#voice");
  const current = voice.value;
  voice.replaceChildren(...VOICES[provider].map((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    return option;
  }));
  if (VOICES[provider].includes(current)) voice.value = current;
  $("#model-field").hidden = provider !== "gemini_api_tts";
  $("#visible-field").hidden = provider === "gemini_api_tts";
  $("#max-chars").value = provider === "gemini_api_tts" ? "2500" : provider === "gemini_web" ? "1600" : "1800";
}

function updateProviderUI() {
  const provider = selectedProvider();
  $$(".radio-segment").forEach((label) => label.classList.toggle("active", label.querySelector("input").checked));
  const status = $("#provider-state");
  const ready = provider === "gemini_api_tts" ? state.system.gemini_api_key : state.system.chrome_available;
  status.classList.toggle("warn", !ready);
  status.textContent = provider === "gemini_api_tts"
    ? t(ready ? "apiReady" : "apiMissing")
    : t(ready ? "browserReady" : "browserMissing");
  $("#submit-job").disabled = state.submitting || !ready;
}

function switchSource(kind) {
  $("#source-kind").value = kind;
  $("#file-source").hidden = kind !== "file";
  $("#text-source").hidden = kind !== "text";
  $$('[data-source-tab]').forEach((button) => {
    const active = button.dataset.sourceTab === kind;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function statusLabel(status) { return t(status) || status; }
function activeStatus(status) { return ["queued", "running", "cancelling"].includes(status); }
function attentionStatus(status) { return ["failed", "cancelled"].includes(status); }

function renderSummary() {
  $("#active-count").textContent = state.jobs.filter((job) => activeStatus(job.status)).length;
  $("#done-count").textContent = state.jobs.filter((job) => job.status === "completed").length;
  $("#failed-count").textContent = state.jobs.filter((job) => attentionStatus(job.status)).length;
}

function renderJobs() {
  renderSummary();
  const list = $("#job-list");
  $("#empty-state").hidden = state.jobs.length > 0;
  list.hidden = state.jobs.length === 0;
  list.innerHTML = state.jobs.map((job) => {
    const provider = String(job.settings?.provider || "unknown").replaceAll("_", " ");
    const progress = Number(job.progress) || 0;
    return `
    <button class="job-row${state.selectedId === job.id ? " selected" : ""}" data-job-id="${job.id}" type="button" aria-label="${escapeHtml(`${job.input_name}, ${statusLabel(job.status)}, ${progress}%`)}">
      <span class="status-dot ${escapeHtml(job.status)}"></span>
      <span class="job-main">
        <strong title="${escapeHtml(job.input_name)}">${escapeHtml(job.input_name)}</strong>
        <span class="job-sub"><span>${escapeHtml(provider)}</span><span>·</span><span>${escapeHtml(statusLabel(job.status))}</span></span>
        <span class="progress-track" role="progressbar" aria-label="${escapeHtml(t("progress"))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><span style="width:${progress}%"></span></span>
      </span>
      <span class="job-progress">${job.progress_text || `${progress}%`}</span>
      <span class="row-action" aria-hidden="true"><img class="ui-icon" src="/static/icons/chevron-right.svg" alt=""></span>
    </button>
  `;
  }).join("");
  $$(".job-row", list).forEach((row) => row.addEventListener("click", () => selectJob(row.dataset.jobId)));
  renderDetail();
}

function renderDetail() {
  const panel = $("#job-detail");
  const job = state.jobs.find((item) => item.id === state.selectedId);
  if (!job) { panel.hidden = true; return; }
  panel.hidden = false;
  $("#detail-title").textContent = job.input_name;
  $("#detail-dot").className = `status-dot ${job.status}`;
  const progress = Number(job.progress) || 0;
  $("#detail-progress").style.width = `${progress}%`;
  $("#detail-progress-track").setAttribute("aria-label", t("progress"));
  $("#detail-progress-track").setAttribute("aria-valuenow", String(progress));
  const settings = job.settings || {};
  const heartbeat = job.heartbeat || {};
  $("#detail-meta").innerHTML = [
    statusLabel(job.status), String(settings.provider || "unknown").replaceAll("_", " "), settings.voice,
    heartbeat.label || heartbeat.stage || job.message,
  ].filter(Boolean).map((value) => `<span>${escapeHtml(value)}</span>`).join("");

  const actions = $("#detail-actions");
  actions.innerHTML = "";
  if (activeStatus(job.status)) {
    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "danger";
    stop.innerHTML = `<img class="ui-icon" src="/static/icons/square.svg" alt=""><span>${escapeHtml(t("stop"))}</span>`;
    stop.addEventListener("click", () => stopJob(job.id));
    actions.append(stop);
  }
  if (job.download_ready) {
    const download = document.createElement("a");
    download.href = `/api/jobs/${job.id}/download`;
    download.innerHTML = `<img class="ui-icon" src="/static/icons/download.svg" alt=""><span>${escapeHtml(t("download"))}</span>`;
    actions.append(download);
  }
  if (["completed", "failed", "cancelled"].includes(job.status)) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "danger";
    remove.innerHTML = `<img class="ui-icon" src="/static/icons/x.svg" alt=""><span>${escapeHtml(t("remove"))}</span>`;
    remove.addEventListener("click", () => deleteJob(job.id));
    actions.append(remove);
  }
  const player = $("#audio-player");
  player.hidden = !job.download_ready;
  const audioSource = `/api/jobs/${job.id}/download?inline=1`;
  if (job.download_ready && player.getAttribute("src") !== audioSource) player.src = audioSource;
  if (!job.download_ready && player.hasAttribute("src")) {
    player.removeAttribute("src");
    player.load();
  }
}

async function selectJob(jobId) {
  if (state.selectedId !== jobId) {
    state.selectedId = jobId;
    state.logOffset = 0;
    state.logText = "";
  }
  renderJobs();
  await refreshLog();
}

async function refreshJobs() {
  if (state.polling) return;
  state.polling = true;
  try {
    const data = await api("/api/jobs");
    state.jobs = data.jobs;
    if (state.selectedId && !state.jobs.some((job) => job.id === state.selectedId)) state.selectedId = null;
    renderJobs();
    if (state.selectedId) await refreshLog();
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.polling = false;
  }
}

async function refreshLog() {
  if (!state.selectedId) return;
  try {
    const data = await api(`/api/jobs/${state.selectedId}/log?offset=${state.logOffset}`);
    if (data.truncated) state.logText = "";
    if (data.text) state.logText += data.text;
    state.logOffset = data.next_offset;
    const log = $("#job-log");
    log.textContent = state.logText || t("noLog");
    if (data.text) log.scrollTop = log.scrollHeight;
  } catch (_) { /* The job may have been deleted between polls. */ }
}

async function stopJob(jobId) {
  try { await api(`/api/jobs/${jobId}/stop`, { method: "POST" }); await refreshJobs(); }
  catch (error) { toast(error.message, true); }
}

async function deleteJob(jobId) {
  if (!window.confirm(t("confirmDelete"))) return;
  try {
    await api(`/api/jobs/${jobId}`, { method: "DELETE" });
    if (state.selectedId === jobId) state.selectedId = null;
    await refreshJobs();
  } catch (error) { toast(error.message, true); }
}

async function submitJob(event) {
  event.preventDefault();
  const kind = $("#source-kind").value;
  const errorNode = $("#form-error");
  errorNode.hidden = true;
  if (kind === "file" && !$("#source-file").files.length) {
    errorNode.textContent = t("selectFile"); errorNode.hidden = false; return;
  }
  if (kind === "text" && !$("#direct-text").value.trim()) {
    errorNode.textContent = t("enterText"); errorNode.hidden = false; return;
  }
  const button = $("#submit-job");
  state.submitting = true;
  button.disabled = true;
  try {
    const formData = new FormData(event.currentTarget);
    const data = await api("/api/jobs", { method: "POST", body: formData });
    toast(t("created"));
    state.selectedId = data.job.id;
    state.logOffset = 0;
    state.logText = "";
    event.currentTarget.reset();
    $('input[name="provider"][value="gemini_api_tts"]').checked = true;
    switchSource("file");
    updateVoiceOptions();
    updateProviderUI();
    $("#file-label").textContent = t("chooseFile");
    await refreshJobs();
  } catch (error) {
    errorNode.textContent = error.message || t("unknownError");
    errorNode.hidden = false;
  } finally {
    state.submitting = false;
    updateProviderUI();
  }
}

async function loadSystem() {
  try {
    state.system = await api("/api/system");
    const items = [
      `<span class="system-pill ${state.system.chrome_available ? "ok" : "warn"}">Chrome</span>`,
      `<span class="system-pill ${state.system.ffmpeg_available ? "ok" : "warn"}">FFmpeg</span>`,
      `<span class="system-pill ${state.system.gemini_api_key ? "ok" : "warn"}">API</span>`,
    ];
    $("#system-summary").innerHTML = items.join("");
    updateProviderUI();
  } catch (error) { toast(error.message, true); }
}

function bindEvents() {
  $$('[data-lang]').forEach((button) => button.addEventListener("click", () => {
    state.language = button.dataset.lang;
    localStorage.setItem("audiobook-language", state.language);
    applyLanguage();
  }));
  $$('[data-source-tab]').forEach((button) => button.addEventListener("click", () => switchSource(button.dataset.sourceTab)));
  $$('input[name="provider"]').forEach((input) => input.addEventListener("change", () => { updateVoiceOptions(); updateProviderUI(); }));
  $("#source-file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    $("#file-label").textContent = file ? file.name : t("chooseFile");
  });
  const zone = $("#drop-zone");
  ["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => { event.preventDefault(); zone.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((name) => zone.addEventListener(name, () => zone.classList.remove("dragging")));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    if (event.dataTransfer.files.length) {
      const transfer = new DataTransfer();
      transfer.items.add(event.dataTransfer.files[0]);
      $("#source-file").files = transfer.files;
      $("#file-label").textContent = transfer.files[0].name;
    }
  });
  $("#job-form").addEventListener("submit", submitJob);
  $("#refresh-jobs").addEventListener("click", refreshJobs);
  $("#close-detail").addEventListener("click", () => { state.selectedId = null; renderJobs(); });
  $("#copy-log").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(state.logText || "");
      toast(t("copied"));
    } catch (error) {
      toast(error.message || t("unknownError"), true);
    }
  });
}

async function init() {
  bindEvents();
  applyLanguage();
  updateVoiceOptions();
  await Promise.all([loadSystem(), refreshJobs()]);
  setInterval(refreshJobs, 2000);
}

document.addEventListener("DOMContentLoaded", init);
