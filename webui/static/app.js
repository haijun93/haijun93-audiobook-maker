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
    download: "다운로드", remove: "삭제", queued: "대기 중", running: "처리 중", recovering: "복구 감시 중", cancelling: "중단 중",
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
    liveOperations: "실시간 작업", connecting: "연결 중", liveConnected: "실시간 연결됨", liveReconnecting: "재연결 중",
    runtimeActive: "실행 중", runtimeHealthy: "정상", runtimeRecovering: "자동 복구", runtimeEmpty: "실행 중인 외부 작업 없음",
    operationsAudit: "30분 운영 감사", auditHealthy: "새 문제 없음", auditNext: "다음 점검", auditFindings: "발견", auditActions: "자동 개선", auditErrors: "신규 오류",
    external: "외부 실행", cooldown: "제한 대기", pacing: "속도 조절", waiting: "재시도 대기", idle_no_work: "대기 작업 없음", degraded: "자동 진단 중",
    stalled: "응답 없음", paused: "일시 정지", interrupted: "중단 감지", reconnecting: "프로세스 확인 중",
    eta: "예상", heartbeatNow: "방금", perHour: "시간당",
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
    download: "Download", remove: "Delete", queued: "Queued", running: "Processing", recovering: "Recovering", cancelling: "Stopping",
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
    liveOperations: "Live operations", connecting: "Connecting", liveConnected: "Live", liveReconnecting: "Reconnecting",
    runtimeActive: "Active", runtimeHealthy: "Healthy", runtimeRecovering: "Auto recovery", runtimeEmpty: "No external work is running",
    operationsAudit: "30-minute operations audit", auditHealthy: "No new issues", auditNext: "Next audit", auditFindings: "Findings", auditActions: "Auto fixes", auditErrors: "New errors",
    external: "External", cooldown: "Cooldown", pacing: "Pacing", waiting: "Waiting", idle_no_work: "No queued work", degraded: "Diagnosing",
    stalled: "Unresponsive", paused: "Paused", interrupted: "Interrupted", reconnecting: "Checking process",
    eta: "ETA", heartbeatNow: "Now", perHour: "per hour",
  },
};

const VOICES = {
  edge_tts: [
    { id: "ko-KR-SunHiNeural", name: "선희 (한국어 여성, 부드러움)" },
    { id: "ko-KR-InJoonNeural", name: "인준 (한국어 남성, 신뢰감)" },
    { id: "ko-KR-HyunsuMultilingualNeural", name: "현수 (한국어/다국어 남성)" },
    { id: "en-US-AvaNeural", name: "Ava (English Female, Natural)" },
    { id: "en-US-AndrewNeural", name: "Andrew (English Male, Warm)" },
    { id: "en-US-EmmaNeural", name: "Emma (English Female, Crisp)" },
    { id: "en-US-BrianNeural", name: "Brian (English Male, Deep)" },
    { id: "en-US-JennyNeural", name: "Jenny (English Female, Storyteller)" },
    { id: "en-US-GuyNeural", name: "Guy (English Male, News/Narration)" },
  ],
  gemini_api_tts: [
    { id: "Sulafat", name: "Sulafat (기본)" },
    { id: "Kore", name: "Kore" },
    { id: "Aoede", name: "Aoede" },
    { id: "Charon", name: "Charon" },
    { id: "Fenrir", name: "Fenrir" },
    { id: "Leda", name: "Leda" },
    { id: "Orus", name: "Orus" },
    { id: "Puck", name: "Puck" },
    { id: "Zephyr", name: "Zephyr" },
  ],
  gemini_web: [{ id: "account_default", name: "계정 기본 음성" }],
  chatgpt_web: [
    { id: "cove", name: "Cove" },
    { id: "fathom", name: "Fathom" },
    { id: "orbit", name: "Orbit" },
    { id: "vale", name: "Vale" },
    { id: "glimmer", name: "Glimmer" },
    { id: "juniper", name: "Juniper" },
    { id: "maple", name: "Maple" },
    { id: "breeze", name: "Breeze" },
    { id: "ember", name: "Ember" },
  ],
};

const state = {
  language: localStorage.getItem("audiobook-language") || "ko",
  task: "audio", system: {}, jobs: [], selectedId: null, logOffset: 0, logText: "", polling: false,
  submitting: { audio: false, translation: false, batch: false },
  progressHistory: {},
  runtime: { summary: {}, workflows: [] }, runtimeStream: null, runtimeLastMessage: 0, runtimeConnection: "connecting",
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
  if (provider === "edge_tts") return true;
  return provider === "gemini_api_tts" ? Boolean(state.system.gemini_api_key) : Boolean(state.system.chrome_available);
}

function providerStatus(provider) {
  const ready = providerReady(provider);
  let text = t(ready ? "browserReady" : "browserMissing");
  if (provider === "edge_tts") {
    text = t("edgeTtsReady");
  } else if (provider === "gemini_api_tts") {
    text = t(ready ? "apiReady" : "apiMissing");
  }
  return {
    ready,
    text,
  };
}

function setVoiceOptions(form, select) {
  const provider = selectedValue(form, "provider", "edge_tts");
  const current = select.value;
  const voiceList = VOICES[provider] || [];
  select.replaceChildren(...voiceList.map((item) => {
    const option = document.createElement("option");
    if (typeof item === "object") {
      option.value = item.id;
      option.textContent = item.name;
    } else {
      option.value = item;
      option.textContent = item;
    }
    return option;
  }));
  const validValues = voiceList.map(v => typeof v === "object" ? v.id : v);
  if (validValues.includes(current)) select.value = current;
}

function updateAudioProviderUI() {
  const form = $("#audio-form");
  const provider = selectedValue(form, "provider", "edge_tts");
  const status = providerStatus(provider);
  $("#audio-provider-state").textContent = status.text;
  $("#audio-provider-state").classList.toggle("warn", !status.ready);
  $("#audio-model-field").hidden = provider !== "gemini_api_tts";
  $("#audio-visible-field").hidden = provider === "gemini_api_tts" || provider === "edge_tts";
  if (form.dataset.activeProvider !== provider) {
    $("#audio-max-chars").value = provider === "edge_tts" ? "4000" : provider === "gemini_api_tts" ? "2500" : provider === "gemini_web" ? "1600" : "1800";
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
  renderRuntime();
  setRuntimeConnection(state.runtimeConnection);
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
function activeStatus(status) { return ["queued", "running", "recovering", "cancelling"].includes(status); }
function attentionStatus(status) { return ["failed", "cancelled"].includes(status); }
function jobTypeLabel(type) {
  return t({ audio: "audioJob", translation: "translationJob", batch_translation: "batchTranslationJob", batch_audio: "batchAudioJob" }[type] || "audioJob");
}

const PIPELINE_STAGE_MAP = {
  translation_browser_launch: "stageBrowserLaunch",
  translation_attempt_start: "stageWaiting",
  wait_for_response: "stageWaiting",
  translation_request_pacing: "stagePacing",
  chatgpt_request_pacing: "stagePacing",
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

const RUNTIME_WORKFLOW_LABELS = {
  study_note_backfill: { ko: "학습노트 백필", en: "Study-note backfill" },
  epub_translation: { ko: "EPUB 번역", en: "EPUB translation" },
  audiobook_generation: { ko: "오디오 생성", en: "Audiobook generation" },
  workflow_runner: { ko: "일괄 워크플로", en: "Batch workflow" },
};

const RUNTIME_STAGE_LABELS = {
  startup: { ko: "시작 준비", en: "Starting" },
  request_notes: { ko: "학습노트 생성", en: "Generating study notes" },
  wait_for_response: { ko: "응답 수신 중", en: "Receiving response" },
  prompt_submitted: { ko: "요청 전송 완료", en: "Request submitted" },
  conversation_rate_limit_wait: { ko: "대화 제한 해제 대기", en: "Conversation cooldown" },
  conversation_rate_limit_recover_done: { ko: "새 대화에서 재개 준비", en: "Resuming in a fresh conversation" },
  rate_limit_wait: { ko: "요청 제한 해제 대기", en: "Rate-limit cooldown" },
  translation_request_pacing: { ko: "다음 번역 요청 대기", en: "Pacing next request" },
  chatgpt_request_pacing: { ko: "ChatGPT 안전 요청 간격 조절", en: "Pacing ChatGPT requests" },
  section_attempt_start: { ko: "음성 합성 요청", en: "Requesting speech" },
  combine_audio: { ko: "오디오 결합 중", en: "Combining audio" },
  validate_cache: { ko: "🛠️ [후처리] 번역 캐시 무결성 검증", en: "Validating translation cache" },
  build_epub: { ko: "🛠️ [후처리] [k-e] 한영 대역본 EPUB 패키징", en: "Building [k-e] EPUB" },
  build_study_epub: { ko: "🛠️ [후처리] [study] 학습노트본 EPUB 생성", en: "Building [study] EPUB" },
  final_tone_review: { ko: "🛠️ [후처리] 문체/어미 일관성 검수", en: "Reviewing tone consistency" },
  final_dialogue_review_pass2: { ko: "🛠️ [후처리] 대화체/존비칭 2차 검수", en: "Reviewing dialogue consistency" },
  final_terminology_review: { ko: "🛠️ [후처리] 고유명사/용어집 일치성 검수", en: "Reviewing terminology" },
  final_presentation_review: { ko: "🛠️ [후처리] EPUB 뷰어 렌더링 검수", en: "Reviewing presentation" },
  final_quality_audit: { ko: "🛠️ [후처리] 완역 품질 게이트 검증", en: "Auditing final quality" },
  post_commands: { ko: "🛠️ [후처리] [k] 및 [e-s] 4대 에디션 조립/추출", en: "Generating [k] and [e-s] editions" },
  finalize: { ko: "🛠️ [후처리] 4대 에디션 서재 최종 배포", en: "Deploying 4 editions to library" },
  finalize_wait: { ko: "🛠️ [후처리] 서재 배포 대기", en: "Waiting for library deployment" },
  organize_library: { ko: "🛠️ [후처리] 서재 정리 및 아카이빙", en: "Organizing library" },
  complete: { ko: "완료", en: "Complete" },
  done: { ko: "완료", en: "Complete" },
};

const RUNTIME_DIAGNOSIS_LABELS = {
  conversation_rate_limit: { ko: "현재 대화 요청 제한", en: "Conversation rate limit" },
  rate_limit: { ko: "서비스 요청 제한", en: "Provider rate limit" },
  usage_limit: { ko: "계정 사용량 한도", en: "Account usage limit" },
  temporary_service_error: { ko: "서비스 일시 오류", en: "Temporary service error" },
  network_error: { ko: "네트워크 연결 오류", en: "Network error" },
  timeout_or_empty_response: { ko: "응답 시간 초과", en: "Response timeout" },
  profile_in_use: { ko: "브라우저 프로필 사용 중", en: "Browser profile in use" },
  session_expired: { ko: "로그인 세션 만료", en: "Session expired" },
  heartbeat_stale: { ko: "진행 신호 없음", en: "Progress heartbeat stale" },
  progress_stalled: { ko: "30분간 완료 진전 없음", en: "No checkpoint progress for 30 minutes" },
  workflow_interrupted: { ko: "작업 중단 감지", en: "Workflow interruption detected" },
  recovery_wait: { ko: "예약된 복구 대기", en: "Scheduled recovery wait" },
  provider_error_burst: { ko: "서비스 오류 급증", en: "Provider error burst" },
  response_format_error_burst: { ko: "응답 형식 오류 반복", en: "Repeated response format errors" },
  new_errors_observed: { ko: "신규 오류 관찰", en: "New errors observed" },
  gemini_outage: { ko: "Gemini 일시 장애", en: "Gemini temporary outage" },
  child_process_failed: { ko: "작업 프로세스 종료", en: "Worker process exited" },
};

function localizedMapValue(map, key) {
  return map[key]?.[state.language] || String(key || "").replaceAll("_", " ");
}

function formatRuntimeDuration(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  if (value < 60) return `${Math.round(value)}${state.language === "ko" ? "초" : "s"}`;
  if (value < 3600) return `${Math.round(value / 60)}${state.language === "ko" ? "분" : "m"}`;
  const totalMinutes = Math.round(value / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return state.language === "ko" ? `${hours}시간 ${minutes}분` : `${hours}h ${minutes}m`;
}

function runtimeHeartbeatText(age) {
  if (age == null) return "--";
  if (Number(age) < 5) return t("heartbeatNow");
  return state.language === "ko" ? `${formatRuntimeDuration(age)} 전` : `${formatRuntimeDuration(age)} ago`;
}

function runtimeStageText(item) {
  const stage = RUNTIME_STAGE_LABELS[item.stage]
    ? localizedMapValue(RUNTIME_STAGE_LABELS, item.stage)
    : (PIPELINE_STAGE_MAP[item.stage] ? t(PIPELINE_STAGE_MAP[item.stage]) : String(item.stage || "").replaceAll("_", " "));
  return item.stage_label ? `${stage} · ${item.stage_label}` : stage;
}

function getAccountSortOrder(item) {
  if (!item) return 99;
  const acc = String(item.account_id || item.account || "").toLowerCase().trim();
  if (acc === "main" || acc === "gemini1" || acc === "account1") return 1;
  if (acc === "account2" || acc === "gemini2") return 2;
  if (acc === "account3" || acc === "gemini3") return 3;
  if (acc === "chatgpt") return 4;

  const s = (
    String(item.account_id || "") + " " +
    String(item.account || "") + " " +
    String(item.id || "") + " " +
    String(item.label || "") + " " +
    String(item.provider || "") + " " +
    String(item.title || "") + " " +
    String(item.profile_dir || "")
  ).toLowerCase();
  
  if (s.includes("account3") || s.includes("gemini3") || s.includes("ngaytot9") || s.includes("heart of frost")) return 3;
  if (s.includes("account2") || s.includes("gemini2") || s.includes("haijun2be") || s.includes("demon copperhead") || s.includes("beneath the burn")) return 2;
  if (s.includes("chatgpt") || s.includes("thousand splendid")) return 4;
  if (s.includes("main") || s.includes("gemini1") || s.includes("account1") || s.includes("haijun93") || s.includes("auggie") || s.includes("fall risk") || s.includes("gemini")) return 1;
  return 99;
}

function getAccountBadgeInfo(item) {
  const ord = getAccountSortOrder(item);
  if (ord === 1) return { short: "제미나이 1", full: "제미나이 1 (haijun93)", cls: "acc-main" };
  if (ord === 2) return { short: "제미나이 2", full: "제미나이 2 (haijun2be)", cls: "acc-account2" };
  if (ord === 3) return { short: "제미나이 3", full: "제미나이 3 (ngaytot9)", cls: "acc-account3" };
  if (ord === 4) return { short: "ChatGPT", full: "ChatGPT (haijun93)", cls: "acc-chatgpt" };
  return { short: "워커", full: item.account_id || "워커", cls: "acc-main" };
}

function renderRuntime() {
  const snapshot = state.runtime || { summary: {}, workflows: [] };
  const summary = snapshot.summary || {};
  $("#runtime-active-count").textContent = summary.active || 0;
  $("#runtime-healthy-count").textContent = summary.healthy || 0;
  $("#runtime-recovering-count").textContent = summary.recovering || 0;
  $("#runtime-attention-count").textContent = summary.attention || 0;

  const audit = snapshot.operations_audit || {};
  const auditNode = $("#runtime-audit");
  auditNode.hidden = !audit.sequence;
  if (audit.sequence) {
    const auditSummary = audit.summary || {};
    const issues = Number(auditSummary.findings) || 0;
    const actions = Number(auditSummary.actions_applied) || 0;
    const newErrors = Number(auditSummary.new_errors) || 0;
    const nextAt = audit.next_run_at
      ? new Date(audit.next_run_at).toLocaleTimeString(state.language === "ko" ? "ko-KR" : "en-US", { hour: "2-digit", minute: "2-digit" })
      : "--";
    const newest = (audit.findings || []).find((finding) => finding.kind !== "healthy");
    const headline = newest
      ? `${newest.title} · ${localizedMapValue(RUNTIME_DIAGNOSIS_LABELS, newest.kind)}`
      : t("auditHealthy");
    const providerEfficiency = (audit.provider_efficiency || []).map((metric) => {
      const provider = String(metric.provider || "").toLowerCase() === "chatgpt" ? "ChatGPT" : "Gemini";
      const rate = Number(metric.chunks_per_hour || 0).toFixed(1);
      const errors = Math.round(Number(metric.error_rate || 0) * 100);
      return state.language === "ko"
        ? `${provider} ${rate}청크/시간 · 오류 ${errors}%`
        : `${provider} ${rate} chunks/hour · errors ${errors}%`;
    }).join(" | ");
    auditNode.className = `runtime-audit audit-${escapeHtml(audit.status || "healthy")}`;
    auditNode.innerHTML = `
      <div><strong>${escapeHtml(t("operationsAudit"))}</strong><span>${escapeHtml(headline)}</span></div>
      <p><b>${escapeHtml(`${t("auditFindings")} ${issues}`)}</b><b>${escapeHtml(`${t("auditErrors")} ${newErrors}`)}</b><b>${escapeHtml(`${t("auditActions")} ${actions}`)}</b><span>${escapeHtml(`${t("auditNext")} ${nextAt}`)}</span></p>
      ${providerEfficiency ? `<p><span>${escapeHtml(providerEfficiency)}</span></p>` : ""}`;
  }

  const accounts = (snapshot.accounts || []).slice().sort((a, b) => getAccountSortOrder(a) - getAccountSortOrder(b));
  const accountList = $("#runtime-accounts");
  accountList.hidden = accounts.length === 0;
  accountList.innerHTML = accounts.map((account) => {
    const status = String(account.status || "waiting");
    const working = ["running", "external", "reconnecting", "pacing"].includes(status);
    const stateClass = working ? "running" : (["cooldown", "waiting", "degraded"].includes(status) ? "recovering" : status);
    const provider = String(account.provider || "").replaceAll("_", " ");
    const detail = account.message || account.task_id || "";
    const accBadge = getAccountBadgeInfo(account);
    return `
      <article class="runtime-account">
        <span class="status-dot ${escapeHtml(stateClass)}" aria-hidden="true"></span>
        <div><strong>${escapeHtml(accBadge.full || account.label || account.id)}</strong><span>${escapeHtml([provider, detail].filter(Boolean).join(" · "))}</span></div>
        <b class="runtime-status ${escapeHtml(stateClass)}">${escapeHtml(statusLabel(status))}</b>
      </article>`;
  }).join("");

  const workflows = (snapshot.workflows || []).slice().sort((a, b) => getAccountSortOrder(a) - getAccountSortOrder(b));
  const list = $("#runtime-list");
  $("#runtime-empty").hidden = workflows.length > 0;
  list.hidden = workflows.length === 0;
  list.innerHTML = workflows.map((item) => {
    const allowedStatuses = ["running", "recovering", "stalled", "failed", "paused", "interrupted", "reconnecting", "completed"];
    const allowedHealth = ["healthy", "degraded", "stalled", "failed", "paused"];
    const status = allowedStatuses.includes(item.status) ? item.status : "running";
    const health = allowedHealth.includes(item.health) ? item.health : "healthy";
    const progress = item.progress || {};
    const completed = progress.completed == null ? "--" : progress.completed;
    const total = progress.total == null ? "--" : progress.total;
    const percent = Math.min(100, Math.max(0, Number(progress.percent) || 0));
    const provider = String(item.provider || "").replaceAll("_", " ");
    const workflowLabel = localizedMapValue(RUNTIME_WORKFLOW_LABELS, item.workflow);
    const meta = [workflowLabel, provider, item.pid ? `PID ${item.pid}` : null, item.elapsed].filter(Boolean).join(" · ");
    const velocity = progress.units_per_hour
      ? (state.language === "ko" ? `${progress.units_per_hour}개/시간` : `${progress.units_per_hour}/hour`) : "";
    const eta = progress.eta_seconds != null ? `${t("eta")} ${formatRuntimeDuration(progress.eta_seconds)}` : "";
    const progressMeta = [velocity, eta].filter(Boolean).join(" · ");
    const diagnosis = item.diagnosis || null;
    const recovery = item.recovery || null;
    const diagnosisTitle = diagnosis ? localizedMapValue(RUNTIME_DIAGNOSIS_LABELS, diagnosis.kind) : "";
    const diagnosisAction = diagnosis
      ? (recovery?.automatic_retry
        ? (state.language === "ko" ? "자동 대응 후 완료 지점부터 재개" : "Auto recovery will resume from the last checkpoint")
        : (recovery?.action || diagnosis.action || diagnosis.root_cause || ""))
      : "";
    const diagnosisHtml = diagnosis ? `
      <div class="runtime-diagnosis">
        <strong>${escapeHtml(diagnosisTitle)}</strong>
        <span>${escapeHtml(diagnosisAction)}</span>
      </div>` : "";
    const accBadge = getAccountBadgeInfo(item);
    const isPostProc = item.phase === "post_processing" || (item.stage && (item.stage.startsWith("final_") || item.stage.startsWith("build_") || item.stage === "validate_cache" || item.stage === "post_commands" || item.stage === "finalize"));
    const phaseBadge = isPostProc
      ? `<span class="postprocess-stage-tag" style="font-size: 10px; padding: 2px 6px;">🛠️ 로컬 후처리 검수</span>`
      : `<span style="font-size: 10px; font-weight: 700; color: #38bdf8; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 6px; border-radius: 4px;">⚡ 웹 LLM 번역</span>`;

    return `
      <article class="runtime-item health-${health} ${isPostProc ? "postproc-item" : ""}" data-runtime-id="${escapeHtml(item.id)}">
        <div class="runtime-item-header">
          <span class="status-dot ${status}" aria-hidden="true"></span>
          <div class="runtime-item-title">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px; flex-wrap: wrap;">
              <span class="account-tag-badge ${accBadge.cls}" style="font-size: 10px; padding: 2px 6px;">👤 ${escapeHtml(accBadge.short)}</span>
              ${phaseBadge}
              <strong title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</strong>
            </div>
            <span>${escapeHtml(meta)}</span>
          </div>
          <span class="runtime-status ${status}">${escapeHtml(statusLabel(status))}</span>
        </div>
        <div class="runtime-progress-head">
          <span class="runtime-progress-count">${escapeHtml(`${completed}/${total}`)} · ${percent}%</span>
          <span class="runtime-progress-meta">${escapeHtml(progressMeta)}</span>
        </div>
        <div class="progress-track" role="progressbar" aria-label="${escapeHtml(t("progress"))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><span style="width:${percent}%"></span></div>
        <div class="runtime-stage" title="${escapeHtml(item.detail || "")}">
          <span class="runtime-stage-dot" aria-hidden="true"></span>
          <span class="runtime-stage-main">${escapeHtml(runtimeStageText(item))}</span>
          <span class="runtime-heartbeat">${escapeHtml(runtimeHeartbeatText(item.heartbeat?.age_seconds))}</span>
        </div>
        ${diagnosisHtml}
      </article>`;
  }).join("");
}

function setRuntimeConnection(status) {
  state.runtimeConnection = status;
  const signal = $("#runtime-signal");
  signal.classList.toggle("connected", status === "connected");
  signal.classList.toggle("reconnecting", status === "reconnecting");
  $("#runtime-connection").textContent = t(status === "connected" ? "liveConnected" : status === "reconnecting" ? "liveReconnecting" : "connecting");
}

function renderSummary() {
  const a = $("#active-count"); if (a) a.textContent = state.jobs.filter((job) => activeStatus(job.status)).length;
  const d = $("#done-count"); if (d) d.textContent = state.jobs.filter((job) => job.status === "completed").length;
  const f = $("#failed-count"); if (f) f.textContent = state.jobs.filter((job) => attentionStatus(job.status)).length;
}

function renderJobs() {
  renderSummary();
  const list = $("#job-list");
  const empty = $("#empty-state");
  if (!list) return;
  if (empty) empty.hidden = state.jobs.length > 0;
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
  const diagnosis = job.diagnosis || (job.batch || {}).diagnosis || null;
  const recovery = job.recovery || null;
  const diagnosticText = diagnosis ? [
    diagnosis.kind,
    diagnosis.root_cause,
    (recovery || {}).action || diagnosis.action,
  ].filter(Boolean).join("\n") : "";
  const errorText = job.status === "failed"
    ? (job.error_detail || diagnosticText || job.message || "")
    : diagnosticText;
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

function applyRuntimeSnapshot(snapshot) {
  state.runtime = snapshot || { summary: {}, workflows: [] };
  state.runtimeLastMessage = Date.now();
  setRuntimeConnection("connected");
  renderRuntime();
}

async function refreshRuntime() {
  try {
    applyRuntimeSnapshot(await api("/api/runtime"));
  } catch (_) {
    setRuntimeConnection("reconnecting");
  }
}

function connectRuntimeStream() {
  if (!("EventSource" in window)) {
    setInterval(refreshRuntime, 1000);
    return;
  }
  if (state.runtimeStream) state.runtimeStream.close();
  const stream = new EventSource("/api/runtime/stream");
  state.runtimeStream = stream;
  stream.addEventListener("runtime", (event) => {
    try { applyRuntimeSnapshot(JSON.parse(event.data)); }
    catch (_) { setRuntimeConnection("reconnecting"); }
  });
  stream.onopen = () => setRuntimeConnection("connected");
  stream.onerror = () => {
    setRuntimeConnection("reconnecting");
    if (Date.now() - state.runtimeLastMessage > 4000) refreshRuntime();
  };
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

function setupVoicePreviewButtons() {
  const setupBtn = (btnId, selectId, playerElId, formId) => {
    const btn = $(btnId);
    const select = $(selectId);
    const player = $(playerElId);
    const form = $(formId);
    if (!btn || !select || !player || !form) return;

    btn.addEventListener("click", () => {
      const provider = selectedValue(form, "provider", "edge_tts");
      const voice = select.value;
      if (!voice) return;

      const originalHtml = btn.innerHTML;
      btn.innerHTML = "<span>⏳</span> <span>생성 중...</span>";
      btn.disabled = true;

      const audioUrl = `/api/tts/preview?provider=${encodeURIComponent(provider)}&voice=${encodeURIComponent(voice)}&_t=${Date.now()}`;
      player.src = audioUrl;
      player.style.display = "block";
      player.play().then(() => {
        btn.innerHTML = "<span>🔊</span> <span>재생 중...</span>";
      }).catch((e) => {
        console.warn("Preview play error:", e);
      }).finally(() => {
        setTimeout(() => {
          btn.innerHTML = originalHtml;
          btn.disabled = false;
        }, 1500);
      });

      player.onended = () => {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
      };
      player.onerror = () => {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
        toast(t("unknownError"), true);
      };
    });
  };

  setupBtn("#audio-voice-preview-btn", "#audio-voice", "#audio-voice-preview-player", "#audio-form");
  setupBtn("#batch-voice-preview-btn", "#batch-voice", "#batch-voice-preview-player", "#batch-form");
}

async function refreshBatchReport() {
  try {
    const resp = await fetch("/api/batch-report");
    if (!resp.ok) return;
    const data = await resp.json();

    // 1. Next Audit Countdown Timer
    const nextSec = data.next_audit_seconds || 0;
    const min = Math.floor(nextSec / 60);
    const sec = nextSec % 60;
    const timerElem = $("#next-audit-timer");
    if (timerElem) {
      timerElem.textContent = `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    }

    // 2. Account Health Grid
    const accGrid = $("#account-health-grid");
    if (accGrid) {
      const accounts = data.accounts || {};
      const accKeys = ["main", "account2", "account3", "chatgpt"];
      accGrid.innerHTML = accKeys.map((key) => {
        const acc = accounts[key] || {};
        const isOk = acc.logged_in;
        const isWarn = acc.status === "attention" || acc.reason === "session_expired" || !acc.logged_in;
        const statusClass = isOk ? "status-ok" : isWarn ? "status-warn" : "status-err";
        const tagClass = isOk ? "ok" : isWarn ? "warn" : "err";
        const statusText = isOk ? "정상 🟢" : isWarn ? "로그인 필요 🟡" : "오류 🔴";
        const accInfo = getAccountBadgeInfo({ id: key });
        const label = accInfo.full || acc.label || key;
        const msg = acc.message || (isOk ? "실시간 번역 작업 정상 수행 중" : "세션 재연결 대기");

        return `
          <div class="account-health-card ${statusClass}">
            <div class="acc-card-header">
              <span class="acc-name">${escapeHtml(label)}</span>
              <span class="acc-status-tag ${tagClass}">${statusText}</span>
            </div>
            <div class="acc-card-msg">${escapeHtml(msg)}</div>
          </div>
        `;
      }).join("");
    }

    // 3. Batch Summary Metrics (총 작업대상, 작업 중, 완료, 남은 개수)
    const summary = data.summary || {};
    const totalCount = summary.total != null ? summary.total : (data.completed_timeline?.length || 0) + (data.active_tasks?.length || 0);
    const activeCount = summary.active != null ? summary.active : (data.active_tasks?.length || 0);
    const completedCount = summary.completed != null ? summary.completed : (data.completed_timeline?.length || 0);
    const remainingCount = summary.remaining != null ? summary.remaining : Math.max(0, totalCount - completedCount);

    const statTotalEl = $("#batch-stat-total");
    const statActiveEl = $("#batch-stat-active");
    const statCompEl = $("#batch-stat-completed");
    const statRemEl = $("#batch-stat-remaining");

    if (statTotalEl) statTotalEl.textContent = `${totalCount}권`;
    if (statActiveEl) statActiveEl.textContent = `${activeCount}권`;
    if (statCompEl) statCompEl.textContent = `${completedCount}권`;
    if (statRemEl) statRemEl.textContent = `${remainingCount}권`;

    // 4. Real-time Tasks (Web Translation vs Local Post-Processing)
    const translationTasks = (data.translation_tasks || (data.active_tasks || []).filter(t => t.phase !== "post_processing")).slice().sort((a, b) => getAccountSortOrder(a) - getAccountSortOrder(b));
    const postprocessTasks = (data.postprocess_tasks || (data.active_tasks || []).filter(t => t.phase === "post_processing")).slice().sort((a, b) => getAccountSortOrder(a) - getAccountSortOrder(b));

    const tasksContainer = $("#active-tasks-container");
    const countBadge = $("#active-tasks-count");
    if (countBadge) {
      countBadge.textContent = `${translationTasks.length}권 번역 중`;
    }

    if (tasksContainer) {
      if (translationTasks.length === 0) {
        tasksContainer.innerHTML = `<div class="empty-state-small">현재 활성화된 본문 번역 작업이 없습니다.</div>`;
      } else {
        tasksContainer.innerHTML = translationTasks.map((t) => {
          const pct = t.progress_percent || 0;
          const labelText = t.label || `진행률 ${pct}%`;
          const speedText = t.speed_cph ? `${t.speed_cph} chunks/h` : "--";
          const etaText = t.eta_minutes ? `예상 ${t.eta_minutes}분` : "";
          const accBadge = getAccountBadgeInfo(t);

          return `
            <div class="task-progress-card">
              <div class="task-card-row-top">
                <div class="task-card-title">
                  <span class="account-tag-badge ${accBadge.cls}" style="font-size: 10px; padding: 2px 6px;">👤 ${escapeHtml(accBadge.short)}</span>
                  <span>📖</span>
                  <span>${escapeHtml(t.title)}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span class="task-progress-pct-bold">${pct}%</span>
                </div>
              </div>
              <div class="task-progress-bar-wrap">
                <div class="task-progress-bar-fill" style="width: ${Math.min(100, Math.max(2, pct))}%"></div>
              </div>
              <div class="task-card-row-bottom">
                <span class="task-label-detail">${escapeHtml(labelText)}</span>
                <div class="task-speed-eta">
                  <span>⚡ ${speedText}</span>
                  ${etaText ? `<span>⏱️ ${etaText}</span>` : ""}
                </div>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    // 4-2. Post-Processing Tasks Container
    const postContainer = $("#postprocess-tasks-container");
    const postCountBadge = $("#postprocess-tasks-count");
    if (postCountBadge) {
      postCountBadge.textContent = `${postprocessTasks.length}권 검수/조립 중`;
    }

    if (postContainer) {
      if (postprocessTasks.length === 0) {
        postContainer.innerHTML = `<div class="empty-state-small">현재 대기/진행 중인 후처리 작업이 없습니다.</div>`;
      } else {
        postContainer.innerHTML = postprocessTasks.map((t) => {
          const accBadge = getAccountBadgeInfo(t);
          const stageKorean = t.stage_korean || t.label || t.stage || "후처리 진행 중";
          const detailText = t.detail || t.last_error || "로컬 고속 검수 및 4대 에디션 자동 패키징/배포 진행 중";

          return `
            <div class="postprocess-task-card">
              <div class="task-card-row-top">
                <div class="task-card-title">
                  <span class="account-tag-badge ${accBadge.cls}" style="font-size: 10px; padding: 2px 6px;">👤 ${escapeHtml(accBadge.short)}</span>
                  <span>📖</span>
                  <span style="font-weight: 700;">${escapeHtml(t.title)}</span>
                </div>
                <span class="postprocess-stage-tag">🛠️ ${escapeHtml(stageKorean)}</span>
              </div>
              <div class="task-card-row-bottom" style="font-size: 11px; color: #94a3b8;">
                <span>${escapeHtml(detailText)}</span>
                <span style="font-size: 10px; color: #a78bfa; font-weight: 600;">(로컬 CPU 전산 처리 💻)</span>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    // 5. Completed Timeline (시간대별 번역 완료 작품 및 처리 계정 - 최근 3일)
    const timelineContainer = $("#completed-timeline-container");
    const compCountBadge = $("#completed-timeline-count");
    const timeline = data.completed_timeline || [];
    if (compCountBadge) {
      compCountBadge.textContent = `${timeline.length}권 완료 (최근 3일)`;
    }

    if (timelineContainer) {
      if (timeline.length === 0) {
        timelineContainer.innerHTML = `<div class="empty-list-text">최근 3일간 번역 완료된 도서가 없습니다.</div>`;
      } else {
        timelineContainer.innerHTML = timeline.map((t) => {
          let dateStr = "";
          let timeStr = "--:--";
          if (t.completed_at) {
            try {
              const d = new Date(t.completed_at);
              const m = d.getMonth() + 1;
              const day = d.getDate();
              const hrs = String(d.getHours()).padStart(2, "0");
              const mins = String(d.getMinutes()).padStart(2, "0");
              dateStr = `${m}/${day}`;
              timeStr = `${hrs}:${mins}`;
            } catch (e) {}
          }
          const accClass = `acc-${t.account_id || "main"}`;
          const formattedDateTime = dateStr ? `${dateStr} ${timeStr}` : timeStr;

          return `
            <div class="timeline-card">
              <div class="timeline-left">
                <span class="timeline-time-badge">🕒 ${escapeHtml(formattedDateTime)}</span>
                <span class="timeline-book-title">${escapeHtml(t.title)}</span>
              </div>
              <div class="timeline-right">
                ${t.duration_text ? `<span class="timeline-duration-badge">⏱️ ${escapeHtml(t.duration_text)}</span>` : ""}
                <span class="account-tag-badge ${accClass}">👤 ${escapeHtml(t.account_label || t.account_id)}</span>
                <span style="font-size: 11px; font-weight: 700; color: #16a34a;">완료 🏆</span>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    // 5. Audit History
    const auditList = $("#audit-history-list");
    if (auditList) {
      const history = (data.audit_history || []).slice().reverse();
      if (history.length === 0) {
        auditList.innerHTML = `<div class="empty-list-text">최근 기록된 감사 이력이 없습니다.</div>`;
      } else {
        auditList.innerHTML = history.slice(0, 4).map((h) => {
          const timeStr = h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "--";
          const findings = h.findings || 0;
          const critical = h.critical || 0;
          const actions = h.actions_applied || 0;
          return `
            <div class="audit-history-item">
              <div class="audit-history-header">
                <span>🕒 ${timeStr} 점검</span>
                <span>조치: ${actions}건</span>
              </div>
              <div class="audit-history-findings">발견 문제: ${findings}건 (치명적: ${critical}건)</div>
            </div>
          `;
        }).join("");
      }
    }
  } catch (err) {
    console.warn("Failed to refresh batch report:", err);
  }
}

function bindEvents() {
  setupVoicePreviewButtons();
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
  
  const refreshBatchBtn = $("#refresh-batch-report");
  if (refreshBatchBtn) {
    refreshBatchBtn.addEventListener("click", async () => {
      refreshBatchBtn.disabled = true;
      toast("30분 정기 점검을 즉시 시작합니다...");
      try {
        await fetch("/api/batch-report/run-check", { method: "POST" });
        setTimeout(refreshBatchReport, 1500);
      } finally {
        setTimeout(() => { refreshBatchBtn.disabled = false; }, 3000);
      }
    });
  }

  const refreshJobsBtn = $("#refresh-jobs");
  if (refreshJobsBtn) refreshJobsBtn.addEventListener("click", refreshJobs);
  const refreshRuntimeBtn = $("#refresh-runtime");
  if (refreshRuntimeBtn) refreshRuntimeBtn.addEventListener("click", refreshRuntime);
  const closeDetailBtn = $("#close-detail");
  if (closeDetailBtn) closeDetailBtn.addEventListener("click", () => { state.selectedId = null; renderJobs(); });
  const copyLogBtn = $("#copy-log");
  if (copyLogBtn) {
    copyLogBtn.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(state.logText || ""); toast(t("copied")); }
      catch (error) { toast(error.message || t("unknownError"), true); }
    });
  }
}

async function init() {
  bindEvents();
  switchTask("audio");
  switchAudioSource("file");
  applyLanguage();
  await Promise.all([loadSystem(), refreshJobs(), refreshRuntime(), refreshBatchReport()]);
  connectRuntimeStream();
  setInterval(refreshBatchReport, 2500);
  setInterval(refreshJobs, 2500);
  setInterval(() => {
    if (Date.now() - state.runtimeLastMessage > 5000) {
      setRuntimeConnection("reconnecting");
      refreshRuntime();
    }
  }, 3000);
}

document.addEventListener("DOMContentLoaded", init);

