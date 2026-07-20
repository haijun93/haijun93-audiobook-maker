const STRINGS = {
  ko: {
    brandSub: "Korean Audiobook Maker", newJob: "새 작업", taskAudio: "오디오", taskTranslation: "도서 번역",
    taskBatch: "폴더 일괄", file: "파일", text: "텍스트", chooseFile: "파일 선택", chooseBook: "영문 도서 선택",
    sourceText: "원문", textPlaceholder: "낭독할 한국어 텍스트를 입력하세요", provider: "음성 제공자",
    translationProvider: "번역 제공자", mode: "구성", modePlain: "원문 낭독", modeMaterial: "자료 중심",
    modeStudy: "학습용", voice: "음성", advanced: "고급 설정", chunkSize: "조각 크기", bitrate: "비트레이트",
    retries: "재시도", model: "모델", showBrowser: "브라우저 창 표시", overwrite: "기존 결과 덮어쓰기",
    conversationChunks: "대화당 조각", outputs: "결과물", bothEditions: "한글 + 한영", koreanEdition: "한글",
    bilingualEdition: "한영", start: "오디오 만들기", startTranslation: "번역 시작", startBatch: "일괄 작업 시작",
    batchOperation: "일괄 작업", translateBooks: "도서 번역", createAudio: "오디오 생성", sourceFolder: "원본 폴더",
    outputFolder: "결과 폴더", defaultOutput: "기본 위치 사용", recursive: "하위 폴더 포함", scan: "검색",
    jobs: "작업", active: "진행 중", ready: "완료", attention: "확인 필요", emptyTitle: "대기 중인 작업이 없습니다",
    emptyBody: "오디오, 번역 또는 폴더 작업을 등록하세요.", log: "실행 로그", copy: "복사", stop: "중단",
    download: "다운로드", remove: "삭제", queued: "대기 중", running: "처리 중", cancelling: "중단 중",
    completed: "완료", failed: "실패", cancelled: "취소됨", created: "작업을 등록했습니다", copied: "로그를 복사했습니다",
    apiReady: "API 키 준비됨", apiMissing: "Gemini API 키 필요", browserReady: "Chrome 준비됨",
    browserMissing: "Chrome 또는 로그인 필요", ffmpegMissing: "FFmpeg 확인 필요", calibreMissing: "MOBI에는 Calibre 필요",
    selectFile: "파일을 선택하세요", enterText: "텍스트를 입력하세요", selectBook: "번역할 도서를 선택하세요",
    enterFolder: "원본 폴더 경로를 입력하세요", unknownError: "요청을 처리하지 못했습니다", noLog: "아직 로그가 없습니다.",
    progress: "진행률", confirmDelete: "이 작업과 내부 저장 결과를 삭제할까요? 외부 폴더의 결과물은 유지됩니다.",
    folderFound: "{total}개 파일 · {counts}", folderEmpty: "지원되는 파일이 없습니다", artifacts: "결과 파일",
    audioJob: "오디오", translationJob: "번역", batchTranslationJob: "일괄 번역", batchAudioJob: "일괄 오디오",
    batchTargets: "대상 파일", batchCompleted: "완료", batchFailedCount: "실패", batchCurrent: "작업 중",
    batchFileList: "파일 목록", batchStatusDone: "완료", batchStatusFailed: "실패", batchStatusSkipped: "건너뜀",
    batchStatusPending: "대기", failureReason: "실패 원인",
    stageBrowserLaunch: "번역 브라우저 시작 중", stageWaiting: "웹 번역 응답 대기 중", stagePacing: "다음 요청 대기 중",
    stagePolishDone: "번역 응답 수신", stageRetrying: "재시도 중", stageFallbackSwitch: "Gemini 과부하 → ChatGPT 웹으로 전환",
    stageGuidePrep: "인물관계/용어 가이드 준비 중", stageFinalReview: "최종 검수 중(말투·용어 일관성)", stageComplete: "완료",
    progressHistoryTitle: "진행 이력 (30분 간격)",
    batchOverallLabel: "전체 배치 진행률",
  },
  en: {
    brandSub: "Korean Audiobook Maker", newJob: "New job", taskAudio: "Audio", taskTranslation: "Translate",
    taskBatch: "Folder batch", file: "File", text: "Text", chooseFile: "Choose a file", chooseBook: "Choose an English book",
    sourceText: "Source text", textPlaceholder: "Enter Korean text to narrate", provider: "Voice provider",
    translationProvider: "Translation provider", mode: "Format", modePlain: "Read source", modeMaterial: "Material only",
    modeStudy: "Study edition", voice: "Voice", advanced: "Advanced", chunkSize: "Chunk size", bitrate: "Bitrate",
    retries: "Retries", model: "Model", showBrowser: "Show browser window", overwrite: "Overwrite existing output",
    conversationChunks: "Chunks per chat", outputs: "Output", bothEditions: "Korean + bilingual", koreanEdition: "Korean",
    bilingualEdition: "Bilingual", start: "Create audio", startTranslation: "Start translation", startBatch: "Start batch",
    batchOperation: "Batch operation", translateBooks: "Translate books", createAudio: "Create audio", sourceFolder: "Source folder",
    outputFolder: "Output folder", defaultOutput: "Use default location", recursive: "Include subfolders", scan: "Scan",
    jobs: "Jobs", active: "Active", ready: "Ready", attention: "Attention", emptyTitle: "No jobs yet",
    emptyBody: "Add an audio, translation, or folder job.", log: "Run log", copy: "Copy", stop: "Stop",
    download: "Download", remove: "Delete", queued: "Queued", running: "Processing", cancelling: "Stopping",
    completed: "Complete", failed: "Failed", cancelled: "Cancelled", created: "Job added", copied: "Log copied",
    apiReady: "API key ready", apiMissing: "Gemini API key required", browserReady: "Chrome ready",
    browserMissing: "Chrome or login required", ffmpegMissing: "Check FFmpeg", calibreMissing: "Calibre required for MOBI",
    selectFile: "Choose a source file", enterText: "Enter source text", selectBook: "Choose a book to translate",
    enterFolder: "Enter a source folder path", unknownError: "The request could not be completed", noLog: "No log output yet.",
    progress: "Progress", confirmDelete: "Delete this job and internally stored output? Files in external folders are kept.",
    folderFound: "{total} files · {counts}", folderEmpty: "No supported files found", artifacts: "Output files",
    audioJob: "Audio", translationJob: "Translation", batchTranslationJob: "Batch translation", batchAudioJob: "Batch audio",
    batchTargets: "Target files", batchCompleted: "Completed", batchFailedCount: "Failed", batchCurrent: "In progress",
    batchFileList: "File list", batchStatusDone: "Done", batchStatusFailed: "Failed", batchStatusSkipped: "Skipped",
    batchStatusPending: "Pending", failureReason: "Failure reason",
    stageBrowserLaunch: "Launching translation browser", stageWaiting: "Waiting for web response", stagePacing: "Pacing before next request",
    stagePolishDone: "Response received", stageRetrying: "Retrying", stageFallbackSwitch: "Gemini overloaded -> switched to ChatGPT web",
    stageGuidePrep: "Preparing relationship/terminology guide", stageFinalReview: "Final review (tone/terminology consistency)", stageComplete: "Complete",
    progressHistoryTitle: "Progress history (every 30 min)",
    batchOverallLabel: "Overall batch progress",
  },
};

const VOICES = {
  gemini_api_tts: ["Sulafat", "Kore", "Aoede", "Charon", "Fenrir", "Leda", "Orus", "Puck", "Zephyr"],
  gemini_web: ["account_default"],
  chatgpt_web: ["cove", "fathom", "orbit", "vale", "glimmer", "juniper", "maple", "breeze", "ember"],
};

const state = {
  language: localStorage.getItem("audiobook-language") || "ko",
  task: "audio", system: {}, jobs: [], selectedId: null, logOffset: 0, logText: "", polling: false,
  submitting: { audio: false, translation: false, batch: false },
  progressHistory: {},
};

const PROGRESS_HISTORY_INTERVAL_MS = 30 * 60 * 1000;

function loadProgressHistory(jobId) {
  if (state.progressHistory[jobId]) return state.progressHistory[jobId];
  try {
    const raw = localStorage.getItem(`audiobook-progress-history-${jobId}`);
    state.progressHistory[jobId] = raw ? JSON.parse(raw) : [];
  } catch (_) {
    state.progressHistory[jobId] = [];
  }
  return state.progressHistory[jobId];
}

function saveProgressHistory(jobId, history) {
  state.progressHistory[jobId] = history;
  try {
    localStorage.setItem(`audiobook-progress-history-${jobId}`, JSON.stringify(history.slice(-200)));
  } catch (_) { /* storage full or unavailable; keep in-memory only */ }
}

function recordProgressSnapshot(job) {
  const history = loadProgressHistory(job.id);
  const last = history[history.length - 1];
  const now = Date.now();
  if (last && now - last.at < PROGRESS_HISTORY_INTERVAL_MS) return;
  const batch = job.batch;
  const heartbeat = job.heartbeat || {};
  history.push({
    at: now,
    total: batch?.total ?? null,
    doneCount: batch ? (batch.completed || []).filter((item) => item.status === "done").length : null,
    failedCount: batch ? (batch.completed || []).filter((item) => item.status === "failed").length : null,
    current: batch?.current || null,
    stageLabel: heartbeat.label || heartbeat.stage || "",
  });
  saveProgressHistory(job.id, history);
}

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

function selectedValue(form, name, fallback = "") {
  return $(`input[name="${name}"]:checked`, form)?.value || fallback;
}

function updateSegmentedControls() {
  $$(".radio-segment").forEach((label) => label.classList.toggle("active", Boolean($("input", label)?.checked)));
}

function providerReady(provider) {
  return provider === "gemini_api_tts" ? Boolean(state.system.gemini_api_key) : Boolean(state.system.chrome_available);
}

function providerStatus(provider) {
  const ready = providerReady(provider);
  return {
    ready,
    text: provider === "gemini_api_tts" ? t(ready ? "apiReady" : "apiMissing") : t(ready ? "browserReady" : "browserMissing"),
  };
}

function setVoiceOptions(form, select) {
  const provider = selectedValue(form, "provider", "gemini_web");
  const current = select.value;
  select.replaceChildren(...VOICES[provider].map((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    return option;
  }));
  if (VOICES[provider].includes(current)) select.value = current;
}

function updateAudioProviderUI() {
  const form = $("#audio-form");
  const provider = selectedValue(form, "provider", "gemini_web");
  const status = providerStatus(provider);
  $("#audio-provider-state").textContent = status.text;
  $("#audio-provider-state").classList.toggle("warn", !status.ready);
  $("#audio-model-field").hidden = provider !== "gemini_api_tts";
  $("#audio-visible-field").hidden = provider === "gemini_api_tts";
  if (form.dataset.activeProvider !== provider) {
    $("#audio-max-chars").value = provider === "gemini_api_tts" ? "2500" : provider === "gemini_web" ? "1600" : "1800";
    form.dataset.activeProvider = provider;
  }
  setVoiceOptions(form, $("#audio-voice"));
  $("#submit-audio").disabled = state.submitting.audio || !status.ready;
  updateSegmentedControls();
}

function updateTranslationProviderUI() {
  const provider = selectedValue($("#translation-form"), "translation_provider", "gemini");
  const status = providerStatus(provider === "gemini" ? "gemini_web" : "chatgpt_web");
  const file = $("#translation-source-file").files[0];
  const mobiBlocked = file?.name.toLowerCase().endsWith(".mobi") && !state.system.ebook_convert_available;
  const node = $("#translation-provider-state");
  node.textContent = mobiBlocked ? t("calibreMissing") : status.text;
  node.classList.toggle("warn", !status.ready || mobiBlocked);
  $("#submit-translation").disabled = state.submitting.translation || !status.ready || mobiBlocked;
  updateSegmentedControls();
}

function updateBatchUI() {
  const form = $("#batch-form");
  const operation = selectedValue(form, "operation", "batch_translation");
  const translating = operation === "batch_translation";
  $("#batch-translation-options").hidden = !translating;
  $("#batch-audio-options").hidden = translating;
  $("#batch-max-chars").min = translating ? "2000" : "200";
  if (form.dataset.activeOperation !== operation) {
    $("#batch-max-chars").value = translating ? "6000" : "1600";
    form.dataset.activeOperation = operation;
  }
  let ready;
  if (translating) {
    const provider = selectedValue(form, "translation_provider", "gemini");
    ready = providerReady(provider === "gemini" ? "gemini_web" : "chatgpt_web");
  } else {
    ready = providerReady(selectedValue(form, "provider", "gemini_web"));
    setVoiceOptions(form, $("#batch-voice"));
  }
  $("#submit-batch").disabled = state.submitting.batch || !ready;
  updateSegmentedControls();
}

function applyLanguage() {
  document.documentElement.lang = state.language;
  $$('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });
  $$('[data-i18n-placeholder]').forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
  $$('[data-lang]').forEach((button) => button.classList.toggle("active", button.dataset.lang === state.language));
  renderJobs();
  updateAudioProviderUI();
  updateTranslationProviderUI();
  updateBatchUI();
}

function switchTask(task) {
  state.task = task;
  $$('[data-task-panel]').forEach((panel) => { panel.hidden = panel.dataset.taskPanel !== task; });
  $$('[data-task-tab]').forEach((button) => {
    const active = button.dataset.taskTab === task;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function switchAudioSource(kind) {
  $("#audio-source-kind").value = kind;
  $("#audio-file-source").hidden = kind !== "file";
  $("#audio-text-source").hidden = kind !== "text";
  $$('[data-audio-source-tab]').forEach((button) => {
    const active = button.dataset.audioSourceTab === kind;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function bindDropZone(zoneSelector, inputSelector, labelSelector, changeCallback = null) {
  const zone = $(zoneSelector);
  const input = $(inputSelector);
  input.addEventListener("change", () => {
    const file = input.files[0];
    $(labelSelector).textContent = file ? file.name : t(inputSelector.includes("translation") ? "chooseBook" : "chooseFile");
    if (changeCallback) changeCallback();
  });
  ["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach((name) => zone.addEventListener(name, () => zone.classList.remove("dragging")));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    if (!event.dataTransfer.files.length) return;
    const transfer = new DataTransfer();
    transfer.items.add(event.dataTransfer.files[0]);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change"));
  });
}

function statusLabel(status) { return t(status) || status; }
function activeStatus(status) { return ["queued", "running", "cancelling"].includes(status); }
function attentionStatus(status) { return ["failed", "cancelled"].includes(status); }
function jobTypeLabel(type) {
  return t({ audio: "audioJob", translation: "translationJob", batch_translation: "batchTranslationJob", batch_audio: "batchAudioJob" }[type] || "audioJob");
}

const PIPELINE_STAGE_MAP = {
  translation_browser_launch: "stageBrowserLaunch",
  translation_attempt_start: "stageWaiting",
  wait_for_response: "stageWaiting",
  translation_request_pacing: "stagePacing",
  translation_response_received: "stagePolishDone",
  translation_retry_sleep: "stageRetrying",
  translation_temporary_error_cooldown: "stageRetrying",
  translation_overnight_provider_switch: "stageFallbackSwitch",
  translation_overnight_provider_switch_resume: "stageFallbackSwitch",
  translation_gemini_subchunk_early: "stageRetrying",
  translation_refusal_subchunk_early: "stageRetrying",
  translation_literary_retry_prompt: "stageRetrying",
  translation_minor_context_retry_prompt: "stageRetrying",
  translation_subchunk_error: "stageRetrying",
  relationship_guide_start: "stageGuidePrep",
  relationship_guide_cached: "stageGuidePrep",
  relationship_guide_complete: "stageGuidePrep",
  relationship_guide_incomplete: "stageGuidePrep",
  relationship_guide_request_error: "stageGuidePrep",
  relationship_guide_local_fallback: "stageGuidePrep",
  relationship_guide_cache_invalid: "stageGuidePrep",
  final_tone_review_complete: "stageFinalReview",
  final_tone_review_failed: "stageFinalReview",
  final_dialogue_review_pass2_complete: "stageFinalReview",
  final_dialogue_review_pass2_failed: "stageFinalReview",
  final_terminology_review_complete: "stageFinalReview",
  final_terminology_review_failed: "stageFinalReview",
  complete: "stageComplete",
};

const PIPELINE_STAGE_KIND = {
  translation_overnight_provider_switch: "fallback",
  translation_overnight_provider_switch_resume: "fallback",
  final_tone_review_complete: "review",
  final_tone_review_failed: "review",
  final_dialogue_review_pass2_complete: "review",
  final_dialogue_review_pass2_failed: "review",
  final_terminology_review_complete: "review",
  final_terminology_review_failed: "review",
  complete: "done",
};

function pipelineStageInfo(heartbeat) {
  const stage = heartbeat?.stage;
  if (!stage || !PIPELINE_STAGE_MAP[stage]) return null;
  return { label: t(PIPELINE_STAGE_MAP[stage]) || stage, kind: PIPELINE_STAGE_KIND[stage] || "gemini" };
}

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
    const progress = Number(job.progress) || 0;
    const provider = String(job.settings?.provider || job.settings?.translation_provider || "").replaceAll("_", " ");
    return `
      <button class="job-row${state.selectedId === job.id ? " selected" : ""}" data-job-id="${job.id}" type="button" aria-label="${escapeHtml(`${job.input_name}, ${statusLabel(job.status)}, ${progress}%`)}">
        <span class="status-dot ${escapeHtml(job.status)}"></span>
        <span class="job-main">
          <strong title="${escapeHtml(job.input_name)}">${escapeHtml(job.input_name)}</strong>
          <span class="job-sub"><span>${escapeHtml(jobTypeLabel(job.job_type))}</span><span>·</span><span>${escapeHtml(provider)}</span><span>·</span><span>${escapeHtml(statusLabel(job.status))}</span></span>
          <span class="progress-track" role="progressbar" aria-label="${escapeHtml(t("progress"))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><span style="width:${progress}%"></span></span>
        </span>
        <span class="job-progress">${job.progress_text || `${progress}%`}</span>
        <span class="row-action" aria-hidden="true"><img class="ui-icon" src="/static/icons/chevron-right.svg" alt=""></span>
      </button>`;
  }).join("");
  $$(".job-row", list).forEach((row) => row.addEventListener("click", () => selectJob(row.dataset.jobId)));
  renderDetail();
}

function renderArtifacts(job) {
  const list = $("#artifact-list");
  const artifacts = job.artifacts || [];
  list.hidden = artifacts.length === 0;
  list.innerHTML = artifacts.length ? artifacts.map((artifact) => `
    <div class="artifact-row">
      <div class="artifact-main">
        <strong title="${escapeHtml(artifact.name)}">${escapeHtml(artifact.name)}</strong>
        <span>${artifact.kind === "audio" ? "M4A" : "EPUB"}</span>
      </div>
      <a href="/api/jobs/${job.id}/artifacts/${artifact.index}" title="${escapeHtml(t("download"))}" aria-label="${escapeHtml(`${t("download")} ${artifact.name}`)}">
        <img src="/static/icons/download.svg" alt="">
      </a>
    </div>`).join("") : "";
}

function renderBatchProgress(job) {
  const panel = $("#batch-progress");
  const batch = job.batch;
  if (!batch || !batch.total) { panel.hidden = true; return; }
  panel.hidden = false;
  $("#batch-total").textContent = batch.total;
  const completedByName = new Map((batch.completed || []).map((item) => [item.name, item]));
  const failedCount = (batch.completed || []).filter((item) => item.status === "failed").length;
  const doneCount = (batch.completed || []).length - failedCount;
  $("#batch-completed-count").textContent = doneCount;
  $("#batch-failed-count").textContent = failedCount;
  const overallPct = batch.total ? Math.min(100, Math.round(((doneCount + failedCount) * 100) / batch.total)) : 0;
  $("#batch-overall-pct").textContent = `${overallPct}%`;
  $("#batch-overall-track > span").style.width = `${overallPct}%`;
  const currentNode = $("#batch-current");
  if (batch.current) {
    currentNode.hidden = false;
    $("#batch-current-name").textContent = batch.current;
  } else {
    currentNode.hidden = true;
  }
  const statusLabel = { done: t("batchStatusDone"), failed: t("batchStatusFailed"), skipped: t("batchStatusSkipped") };
  $("#batch-files").innerHTML = (batch.targets || []).map((name) => {
    const item = completedByName.get(name);
    const status = item?.status;
    const isCurrent = !status && batch.current === name;
    const cls = isCurrent ? "current" : (status || "pending");
    const label = isCurrent ? t("batchCurrent") : (statusLabel[status] || t("batchStatusPending"));
    const errorLine = status === "failed" && item?.error
      ? `<span class="batch-file-error">${escapeHtml(item.error)}</span>` : "";
    return `
      <div class="batch-file-row ${cls}">
        <span class="batch-file-dot" aria-hidden="true"></span>
        <span class="batch-file-main">
          <span class="batch-file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
          ${errorLine}
        </span>
        <span class="batch-file-status">${escapeHtml(label)}</span>
      </div>`;
  }).join("");
}

function formatHistoryTime(ts) {
  const date = new Date(ts);
  return date.toLocaleString(state.language === "ko" ? "ko-KR" : "en-US", { hour: "2-digit", minute: "2-digit", month: "numeric", day: "numeric" });
}

function renderProgressHistory(job) {
  const panel = $("#progress-history");
  if (!panel) return;
  const history = loadProgressHistory(job.id);
  if (!history.length) { panel.hidden = true; return; }
  panel.hidden = false;
  $("#progress-history-list").innerHTML = history.slice().reverse().map((entry) => {
    const counts = entry.total != null ? `${entry.doneCount ?? 0}/${entry.total} (${t("batchFailedCount")} ${entry.failedCount ?? 0})` : "";
    const currentText = entry.current ? ` · ${escapeHtml(entry.current)}` : "";
    const stageText = entry.stageLabel ? ` · ${escapeHtml(entry.stageLabel)}` : "";
    return `<div class="history-row"><strong>${formatHistoryTime(entry.at)}</strong><span>${escapeHtml(counts)}${currentText}${stageText}</span></div>`;
  }).join("");
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
  const heartbeat = job.heartbeat || {};
  const settings = job.settings || {};
  $("#detail-meta").innerHTML = [
    jobTypeLabel(job.job_type), statusLabel(job.status), settings.provider || settings.translation_provider, settings.voice,
    heartbeat.label || heartbeat.stage || job.message,
  ].filter(Boolean).map((value) => `<span>${escapeHtml(String(value).replaceAll("_", " "))}</span>`).join("");

  const stageNode = $("#pipeline-stage");
  const stageInfo = activeStatus(job.status) ? pipelineStageInfo(heartbeat) : null;
  if (stageInfo) {
    stageNode.hidden = false;
    stageNode.className = `pipeline-stage kind-${stageInfo.kind}`;
    $("#pipeline-stage-label").textContent = stageInfo.label;
  } else {
    stageNode.hidden = true;
  }

  const errorPanel = $("#detail-error");
  const errorText = job.status === "failed" ? (job.error_detail || job.message || "") : "";
  errorPanel.hidden = !errorText;
  $("#detail-error-text").textContent = errorText;

  renderBatchProgress(job);
  renderProgressHistory(job);

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
  if (["completed", "failed", "cancelled"].includes(job.status)) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "danger";
    remove.innerHTML = `<img class="ui-icon" src="/static/icons/x.svg" alt=""><span>${escapeHtml(t("remove"))}</span>`;
    remove.addEventListener("click", () => deleteJob(job.id));
    actions.append(remove);
  }
  renderArtifacts(job);
  const audio = (job.artifacts || []).find((artifact) => artifact.kind === "audio");
  const player = $("#audio-player");
  player.hidden = !audio;
  const audioSource = audio ? `/api/jobs/${job.id}/artifacts/${audio.index}?inline=1` : "";
  if (audio && player.getAttribute("src") !== audioSource) player.src = audioSource;
  if (!audio && player.hasAttribute("src")) { player.removeAttribute("src"); player.load(); }
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
    state.jobs.forEach((job) => {
      if (!activeStatus(job.status)) return;
      if (job.batch) recordProgressSnapshot(job);
    });
    renderJobs();
    if (state.selectedId) await refreshLog();
  } catch (error) { toast(error.message, true); }
  finally { state.polling = false; }
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
  } catch (_) { /* A job may be deleted between polls. */ }
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

function showFormError(id, message = "") {
  const node = $(id);
  node.textContent = message;
  node.hidden = !message;
}

async function submitAudio(event) {
  event.preventDefault();
  const kind = $("#audio-source-kind").value;
  if (kind === "file" && !$("#audio-source-file").files.length) return showFormError("#audio-form-error", t("selectFile"));
  if (kind === "text" && !$("#audio-direct-text").value.trim()) return showFormError("#audio-form-error", t("enterText"));
  showFormError("#audio-form-error");
  state.submitting.audio = true;
  updateAudioProviderUI();
  try {
    const data = await api("/api/jobs", { method: "POST", body: new FormData(event.currentTarget) });
    finishSubmission(data.job.id);
  } catch (error) { showFormError("#audio-form-error", error.message || t("unknownError")); }
  finally { state.submitting.audio = false; updateAudioProviderUI(); }
}

async function submitTranslation(event) {
  event.preventDefault();
  if (!$("#translation-source-file").files.length) return showFormError("#translation-form-error", t("selectBook"));
  showFormError("#translation-form-error");
  state.submitting.translation = true;
  updateTranslationProviderUI();
  try {
    const data = await api("/api/jobs/translation", { method: "POST", body: new FormData(event.currentTarget) });
    finishSubmission(data.job.id);
  } catch (error) { showFormError("#translation-form-error", error.message || t("unknownError")); }
  finally { state.submitting.translation = false; updateTranslationProviderUI(); }
}

function batchPayload(form) {
  const payload = Object.fromEntries(new FormData(form).entries());
  ["recursive", "overwrite", "visible"].forEach((name) => { payload[name] = $(`input[name="${name}"]`, form)?.checked || false; });
  return payload;
}

async function scanFolder() {
  const form = $("#batch-form");
  const payload = batchPayload(form);
  const node = $("#folder-scan-result");
  if (!String(payload.source_dir || "").trim()) { node.textContent = t("enterFolder"); node.classList.add("warn"); return; }
  try {
    const result = await api("/api/folders/scan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_dir: payload.source_dir, operation: payload.operation, recursive: payload.recursive }),
    });
    const counts = Object.entries(result.counts).map(([key, value]) => `${key.toUpperCase()} ${value}`).join(" · ");
    node.textContent = result.total ? t("folderFound").replace("{total}", result.total).replace("{counts}", counts) : t("folderEmpty");
    node.classList.toggle("warn", result.total === 0);
  } catch (error) { node.textContent = error.message; node.classList.add("warn"); }
}

async function submitBatch(event) {
  event.preventDefault();
  const payload = batchPayload(event.currentTarget);
  if (!String(payload.source_dir || "").trim()) return showFormError("#batch-form-error", t("enterFolder"));
  showFormError("#batch-form-error");
  state.submitting.batch = true;
  updateBatchUI();
  try {
    const data = await api("/api/jobs/batch", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    finishSubmission(data.job.id);
  } catch (error) { showFormError("#batch-form-error", error.message || t("unknownError")); }
  finally { state.submitting.batch = false; updateBatchUI(); }
}

function finishSubmission(jobId) {
  toast(t("created"));
  state.selectedId = jobId;
  state.logOffset = 0;
  state.logText = "";
  refreshJobs();
}

async function loadSystem() {
  try {
    state.system = await api("/api/system");
    const items = [
      ["Chrome", state.system.chrome_available], ["FFmpeg", state.system.ffmpeg_available],
      ["API", state.system.gemini_api_key], ["Calibre", state.system.ebook_convert_available],
    ];
    $("#system-summary").innerHTML = items.map(([name, ready]) => `<span class="system-pill ${ready ? "ok" : "warn"}">${name}</span>`).join("");
    updateAudioProviderUI();
    updateTranslationProviderUI();
    updateBatchUI();
  } catch (error) { toast(error.message, true); }
}

function bindEvents() {
  $$('[data-lang]').forEach((button) => button.addEventListener("click", () => {
    state.language = button.dataset.lang;
    localStorage.setItem("audiobook-language", state.language);
    applyLanguage();
  }));
  $$('[data-task-tab]').forEach((button) => button.addEventListener("click", () => switchTask(button.dataset.taskTab)));
  $$('[data-audio-source-tab]').forEach((button) => button.addEventListener("click", () => switchAudioSource(button.dataset.audioSourceTab)));
  $$('.audio-provider-control input').forEach((input) => input.addEventListener("change", updateAudioProviderUI));
  $$('.translation-provider-control input, .output-control input').forEach((input) => input.addEventListener("change", updateTranslationProviderUI));
  $$('.batch-operation-control input, .batch-translation-provider-control input, .batch-audio-provider-control input').forEach((input) => input.addEventListener("change", () => {
    $("#folder-scan-result").textContent = "";
    updateBatchUI();
  }));
  bindDropZone("#audio-drop-zone", "#audio-source-file", "#audio-file-label");
  bindDropZone("#translation-drop-zone", "#translation-source-file", "#translation-file-label", updateTranslationProviderUI);
  $("#audio-form").addEventListener("submit", submitAudio);
  $("#translation-form").addEventListener("submit", submitTranslation);
  $("#batch-form").addEventListener("submit", submitBatch);
  $("#scan-folder").addEventListener("click", scanFolder);
  $("#batch-recursive").addEventListener("change", () => { $("#folder-scan-result").textContent = ""; });
  $("#refresh-jobs").addEventListener("click", refreshJobs);
  $("#close-detail").addEventListener("click", () => { state.selectedId = null; renderJobs(); });
  $("#copy-log").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(state.logText || ""); toast(t("copied")); }
    catch (error) { toast(error.message || t("unknownError"), true); }
  });
}

async function init() {
  bindEvents();
  switchTask("audio");
  switchAudioSource("file");
  applyLanguage();
  await Promise.all([loadSystem(), refreshJobs()]);
  setInterval(refreshJobs, 2000);
}

document.addEventListener("DOMContentLoaded", init);
