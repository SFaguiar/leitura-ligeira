import { RSVPEngine, computeOrpIndex } from "./rsvp.js";
import { TTSDriver, describeVoice } from "./tts.js";

const libraryView = document.getElementById("library-view");
const dashboardView = document.getElementById("dashboard-view");
const statsBtn = document.getElementById("stats-btn");
const dashboardBackBtn = document.getElementById("dashboard-back-btn");
const statsScopeButtons = document.querySelectorAll("[data-stats-scope]");
const statsPeriod = document.getElementById("stats-period");
const statsCollect = document.getElementById("stats-collect");
const statsPrivacyNote = document.getElementById("stats-privacy-note");
const statsError = document.getElementById("stats-error");
const statsLoading = document.getElementById("stats-loading");
const statsContent = document.getElementById("stats-content");
const statsWords = document.getElementById("stats-words");
const statsTime = document.getElementById("stats-time");
const statsWpm = document.getElementById("stats-wpm");
const statsStreak = document.getElementById("stats-streak");
const statsCompletion = document.getElementById("stats-completion");
const statsSessions = document.getElementById("stats-sessions");
const statsChartCaption = document.getElementById("stats-chart-caption");
const statsDailyChart = document.getElementById("stats-daily-chart");
const statsChartEmpty = document.getElementById("stats-chart-empty");
const statsModes = document.getElementById("stats-modes");
const statsDocuments = document.getElementById("stats-documents");
const readerView = document.getElementById("reader-view");
const documentList = document.getElementById("document-list");
const libraryEmpty = document.getElementById("library-empty");

const newDocBtn = document.getElementById("new-doc-btn");
const newDocModal = document.getElementById("new-doc-modal");
const docTitleInput = document.getElementById("doc-title");
const docTextInput = document.getElementById("doc-text");
const saveDocBtn = document.getElementById("save-doc-btn");
const cancelDocBtn = document.getElementById("cancel-doc-btn");
const docPrivateInput = document.getElementById("doc-private");
const docError = document.getElementById("doc-error");

const docTabPasteBtn = document.getElementById("doc-tab-paste-btn");
const docTabFileBtn = document.getElementById("doc-tab-file-btn");
const docTabUrlBtn = document.getElementById("doc-tab-url-btn");
const docTabPastePanel = document.getElementById("doc-tab-paste");
const docTabFilePanel = document.getElementById("doc-tab-file");
const docTabUrlPanel = document.getElementById("doc-tab-url");
const docFileTitleInput = document.getElementById("doc-file-title");
const docFileInput = document.getElementById("doc-file-input");
const docUrlTitleInput = document.getElementById("doc-url-title");
const docUrlInput = document.getElementById("doc-url-input");

const tocBtn = document.getElementById("toc-btn");
const tocDropdown = document.getElementById("toc-dropdown");
const tocList = document.getElementById("toc-list");

const backBtn = document.getElementById("back-btn");
const readerTitle = document.getElementById("reader-title");
const rsvpDisplay = document.getElementById("rsvp-display");
const progressFill = document.getElementById("progress-fill");
const scrubber = document.getElementById("scrubber");
const paragraphMarks = document.getElementById("paragraph-marks");
const readingProgressInfo = document.getElementById("reading-progress-info");

const modeFocusBtn = document.getElementById("mode-focus-btn");
const modeFlowBtn = document.getElementById("mode-flow-btn");
const rsvpStage = document.getElementById("rsvp-stage");
const flowRegion = document.getElementById("flow-region");
const flowContent = document.getElementById("flow-content");
const flowBackToPositionBtn = document.getElementById("flow-back-to-position");

const playPauseBtn = document.getElementById("play-pause-btn");
const rewindBtn = document.getElementById("rewind-btn");
const forwardBtn = document.getElementById("forward-btn");
const ttsToggle = document.getElementById("tts-toggle");
const ttsToggleLabel = document.getElementById("tts-toggle-label");
const ttsStatus = document.getElementById("tts-status");
const ttsSettings = document.getElementById("tts-settings");
const ttsVoice = document.getElementById("tts-voice");
const ttsRateSlider = document.getElementById("tts-rate-slider");
const ttsRateValue = document.getElementById("tts-rate-value");
const ttsEffectiveWpm = document.getElementById("tts-effective-wpm");
const ttsBufferSlider = document.getElementById("tts-buffer-slider");
const ttsBufferValue = document.getElementById("tts-buffer-value");
const ttsBufferStatus = document.getElementById("tts-buffer-status");

const wpmRow = document.getElementById("wpm-row");
const wpmSlider = document.getElementById("wpm-slider");
const wpmValue = document.getElementById("wpm-value");
const chunkRow = document.getElementById("chunk-row");
const chunkSlider = document.getElementById("chunk-slider");
const chunkValue = document.getElementById("chunk-value");
const fontSlider = document.getElementById("font-slider");
const fontValue = document.getElementById("font-value");

const orpRow = document.getElementById("orp-row");
const orpToggle = document.getElementById("orp-toggle");
const navSnapBackRow = document.getElementById("nav-snap-back-row");
const navSnapBackToggle = document.getElementById("nav-snap-back-toggle");
const navPauseSwitchToggle = document.getElementById("nav-pause-switch-toggle");

const themeToggle = document.getElementById("theme-toggle");
const skinSelect = document.getElementById("skin-select");
const transportWarning = document.getElementById("transport-warning");

const currentUserName = document.getElementById("current-user-name");
const logoutBtn = document.getElementById("logout-btn");

const loginView = document.getElementById("login-view");
const profileList = document.getElementById("profile-list");
const newProfileBtn = document.getElementById("new-profile-btn");

const loginModal = document.getElementById("login-modal");
const loginModalName = document.getElementById("login-modal-name");
const loginPasswordInput = document.getElementById("login-password");
const loginError = document.getElementById("login-error");
const loginCancelBtn = document.getElementById("login-cancel-btn");
const loginSubmitBtn = document.getElementById("login-submit-btn");

const newProfileModal = document.getElementById("new-profile-modal");
const newProfileNameInput = document.getElementById("new-profile-name");
const newProfilePasswordInput = document.getElementById("new-profile-password");
const newProfileError = document.getElementById("new-profile-error");
const newProfileCancelBtn = document.getElementById("new-profile-cancel-btn");
const newProfileSubmitBtn = document.getElementById("new-profile-submit-btn");

// ---- Transport security ----
async function applyTransportStatus() {
    const isHttps = window.location.protocol === "https:";
    document.documentElement.setAttribute("data-transport", isHttps ? "https" : "http");
    transportWarning.hidden = isHttps;
    if (isHttps) return;
    try {
        const response = await fetch("/system/transport");
        if (!response.ok) return;
        const status = await response.json();
        transportWarning.dataset.lanEnabled = status.lan_enabled ? "true" : "false";
    } catch {
        // The browser protocol remains the authoritative safe fallback.
    }
}

applyTransportStatus();

const abandonedModal = document.getElementById("abandoned-modal");
const abandonedModalTitle = document.getElementById("abandoned-modal-title");
const abandonedResumeBtn = document.getElementById("abandoned-resume-btn");
const abandonedWishlistBtn = document.getElementById("abandoned-wishlist-btn");
const abandonedKeepBtn = document.getElementById("abandoned-keep-btn");

const librarySearchInput = document.getElementById("library-search");
const libraryCollectionFilter = document.getElementById("library-collection-filter");
const shelfTabButtons = document.querySelectorAll(".shelf-tabs .mode-btn");

const editDocModal = document.getElementById("edit-doc-modal");
const editDocTitleInput = document.getElementById("edit-doc-title");
const editDocCollectionInput = document.getElementById("edit-doc-collection");
const editDocCollectionList = document.getElementById("edit-doc-collection-list");
const editDocError = document.getElementById("edit-doc-error");
const editDocCancelBtn = document.getElementById("edit-doc-cancel-btn");
const editDocSaveBtn = document.getElementById("edit-doc-save-btn");

// ---- Settings module (single source of truth) ----
// Everything the reader remembers goes through get/set here, under one
// naming convention. Fase 4 (contas) redirects this module to the server —
// having one seam instead of ~6 scattered localStorage call sites is the
// whole point of doing this now.
const SETTINGS_PREFIX = "settings.";
const SETTINGS_TYPES = {
    theme: "string",
    skin: "string",
    activeMode: "string",
    wpmFocus: "number",
    wpmFlow: "number",
    chunkFocus: "number",
    chunkFlow: "number",
    fontFocus: "number",
    fontFlow: "number",
    orpEnabled: "boolean",
    navSnapBackOnClick: "boolean",
    navPauseOnSwitch: "boolean",
    collectStats: "boolean",
    ttsVoice: "string",
    ttsRate: "number",
    ttsBufferSeconds: "number",
};
const SETTINGS_DEFAULTS = {
    theme: "light",
    skin: "library",
    activeMode: "focus",
    wpmFocus: 300,
    chunkFocus: 1,
    fontFocus: 48,
    chunkFlow: 1,
    fontFlow: 20,
    orpEnabled: false,
    navSnapBackOnClick: false,
    navPauseOnSwitch: false,
    collectStats: true,
    ttsVoice: "pf_dora",
    ttsRate: 1,
    ttsBufferSeconds: 60,
};
// Maps a local settings key to its column name on the server. Fase 4 syncs
// every write here (debounced) so a second device/profile picks it up —
// localStorage stays the instant-read cache, the server is the account's
// source of truth.
const SETTINGS_SERVER_KEYS = {
    theme: "theme",
    skin: "skin",
    activeMode: "active_mode",
    wpmFocus: "wpm_focus",
    wpmFlow: "wpm_flow",
    chunkFocus: "chunk_focus",
    chunkFlow: "chunk_flow",
    fontFocus: "font_focus",
    fontFlow: "font_flow",
    orpEnabled: "orp_enabled",
    navSnapBackOnClick: "nav_snap_back_on_click",
    navPauseOnSwitch: "nav_pause_on_switch",
    collectStats: "collect_stats",
};

function getSetting(key) {
    const raw = localStorage.getItem(SETTINGS_PREFIX + key);
    if (raw === null) {
        // Flow tends to want a slower pace than Focus (eye moves along the
        // line) — seed it a bit below Focus's WPM the first time, instead of
        // a fixed number that ignores what the user already calibrated.
        if (key === "wpmFlow") return Math.max(100, getSetting("wpmFocus") - 50);
        return SETTINGS_DEFAULTS[key];
    }
    if (SETTINGS_TYPES[key] === "boolean") return raw === "1";
    if (SETTINGS_TYPES[key] === "number") return Number(raw);
    return raw;
}

function setSetting(key, value) {
    localStorage.setItem(SETTINGS_PREFIX + key, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
    const serverKey = SETTINGS_SERVER_KEYS[key];
    if (serverKey && currentUser) {
        settingsSyncQueue[serverKey] = value;
        clearTimeout(settingsSyncTimer);
        settingsSyncTimer = setTimeout(flushSettingsSync, 600);
    }
}

// Declared here (ahead of the Auth section below) because applyTheme() at
// module load calls setSetting() synchronously, which reads currentUser —
// that reference would otherwise land in the temporal dead zone.
let currentUser = null;
let settingsSyncQueue = {};
let settingsSyncTimer = null;

async function flushSettingsSync() {
    if (!currentUser) return;
    const body = settingsSyncQueue;
    settingsSyncQueue = {};
    if (Object.keys(body).length === 0) return;
    try {
        await securityFetch("/me/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
    } catch {
        // Best-effort — localStorage already has the value; the next change
        // (or next login's applyServerSettings) reconciles it.
    }
}

// Mirrors settings fetched from the server into the local cache without
// re-queuing a sync — this data just came *from* the server.
function applyServerSettings(s) {
    localStorage.setItem(SETTINGS_PREFIX + "theme", s.theme);
    localStorage.setItem(SETTINGS_PREFIX + "activeMode", s.active_mode);
    localStorage.setItem(SETTINGS_PREFIX + "wpmFocus", String(s.wpm_focus));
    localStorage.setItem(SETTINGS_PREFIX + "wpmFlow", String(s.wpm_flow));
    localStorage.setItem(SETTINGS_PREFIX + "chunkFocus", String(s.chunk_focus));
    localStorage.setItem(SETTINGS_PREFIX + "chunkFlow", String(s.chunk_flow));
    localStorage.setItem(SETTINGS_PREFIX + "fontFocus", String(s.font_focus));
    localStorage.setItem(SETTINGS_PREFIX + "fontFlow", String(s.font_flow));
    localStorage.setItem(SETTINGS_PREFIX + "orpEnabled", s.orp_enabled ? "1" : "0");
    localStorage.setItem(SETTINGS_PREFIX + "navSnapBackOnClick", s.nav_snap_back_on_click ? "1" : "0");
    localStorage.setItem(SETTINGS_PREFIX + "navPauseOnSwitch", s.nav_pause_on_switch ? "1" : "0");
    localStorage.setItem(SETTINGS_PREFIX + "collectStats", s.collect_stats ? "1" : "0");
    localStorage.setItem(SETTINGS_PREFIX + "skin", s.skin);
}

function modeKey(base) {
    return `${base}${activeMode === "focus" ? "Focus" : "Flow"}`;
}

function applySkin(skin) {
    const normalized = skin === "odysseus" ? "odysseus" : "library";
    document.documentElement.setAttribute("data-skin", normalized);
    skinSelect.value = normalized;
    setSetting("skin", normalized);
}

applySkin(getSetting("skin"));
skinSelect.addEventListener("change", () => applySkin(skinSelect.value));

// ---- Theme ----
function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
    setSetting("theme", theme);
}
applyTheme(getSetting("theme"));
themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    applyTheme(current === "dark" ? "light" : "dark");
});

// ---- Auth ----
// Auto-registro aberto, estilo Netflix: a tela de login lista os perfis
// existentes; o primeiro perfil criado no app inteiro vira admin (decidido
// no backend). Sessão via cookie assinado (SessionMiddleware) — apiFetch()
// é o único lugar que reage a uma sessão expirada/inválida. (currentUser is
// declared earlier, in the Settings module, to avoid a TDZ hit — see there.)

let csrfToken = null;
let csrfRequest = null;

function clearCsrfToken() {
    csrfToken = null;
    csrfRequest = null;
}

async function ensureCsrfToken() {
    if (csrfToken) return csrfToken;
    if (!csrfRequest) {
        csrfRequest = fetch("/security/csrf", { cache: "no-store" })
            .then(async (response) => {
                if (!response.ok) throw new Error("Não foi possível iniciar a proteção CSRF.");
                const payload = await response.json();
                if (!payload.token) throw new Error("Token CSRF ausente.");
                csrfToken = payload.token;
                return csrfToken;
            })
            .finally(() => {
                csrfRequest = null;
            });
    }
    return csrfRequest;
}

async function securityFetch(url, options = {}, retried = false) {
    const method = String(options.method || "GET").toUpperCase();
    const unsafe = !["GET", "HEAD", "OPTIONS"].includes(method);
    const requestOptions = { ...options };
    if (unsafe) {
        const headers = new Headers(options.headers || {});
        headers.set("X-CSRF-Token", await ensureCsrfToken());
        requestOptions.headers = headers;
    }
    const response = await fetch(url, requestOptions);
    if (
        unsafe &&
        !retried &&
        response.status === 403 &&
        response.headers.get("X-CSRF-Required") === "1"
    ) {
        clearCsrfToken();
        return securityFetch(url, options, true);
    }
    return response;
}

async function apiFetch(url, options) {
    const res = await securityFetch(url, options);
    if (res.status === 401) {
        currentUser = null;
        clearCsrfToken();
        showLogin();
    }
    return res;
}

async function apiErrorMessage(res, fallback) {
    try {
        const body = await res.json();
        return body.detail || fallback;
    } catch {
        return fallback;
    }
}

function showLogin() {
    // A 401/logout can replace the reader view without passing through
    // showLibrary(); discard any queued Flow work and document DOM here too.
    readerRequestId += 1;
    resetLibraryState();
    cancelStatsRequest();
    stopTtsForLifecycle();
    engine.pause();
    releaseWakeLock();
    resetSessionState();
    resetFlowState();
    currentDocId = null;
    ttsVoicesLoaded = false;
    ttsVoicesRequestId += 1;
    readerView.hidden = true;
    libraryView.hidden = true;
    loginView.hidden = false;
    dashboardView.hidden = true;
    currentUserName.hidden = true;
    logoutBtn.hidden = true;
    loadProfileList();
}

async function loadProfileList() {
    const res = await fetch("/users");
    const users = res.ok ? await res.json() : [];
    profileList.innerHTML = "";
    users.forEach((u) => {
        const li = document.createElement("li");
        li.textContent = u.name;
        li.addEventListener("click", () => openLoginModal(u.name));
        li.dataset.initial = u.name.trim().charAt(0).toUpperCase() || "?";
        li.setAttribute("role", "button");
        li.tabIndex = 0;
        li.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openLoginModal(u.name);
            }
        });
        profileList.appendChild(li);
    });
}

async function afterLogin() {
    currentUserName.textContent = currentUser.name;
    currentUserName.hidden = false;
    logoutBtn.hidden = false;
    loginView.hidden = true;
    try {
        const res = await fetch("/me/settings");
        if (res.ok) {
            applyServerSettings(await res.json());
        }
    } catch {
        // Offline mirror already has whatever was there before — carry on.
    }
    applyTheme(getSetting("theme"));
    applySkin(getSetting("skin"));
    // Voice discovery is best-effort and may wait on the local Kokoro service;
    // it must never hold the library hostage during login.
    loadTtsVoices();
    initFromLocation();
}

function canManage(doc) {
    if (!currentUser) return false;
    if (doc.owner_id === currentUser.id) return true;
    if (currentUser.role === "admin" && doc.visibility === "house") return true;
    return false;
}

let loginTargetName = null;

function openLoginModal(name) {
    loginTargetName = name;
    loginModalName.textContent = name;
    loginPasswordInput.value = "";
    loginError.hidden = true;
    loginModal.hidden = false;
    loginPasswordInput.focus();
}
function closeLoginModal() {
    loginModal.hidden = true;
}
loginCancelBtn.addEventListener("click", closeLoginModal);
loginModal.addEventListener("click", (e) => {
    if (e.target === loginModal) closeLoginModal();
});
loginPasswordInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        loginSubmitBtn.click();
    }
});
loginSubmitBtn.addEventListener("click", async () => {
    const password = loginPasswordInput.value;
    if (!password) {
        loginError.textContent = "Digite a senha.";
        loginError.hidden = false;
        return;
    }
    const res = await securityFetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: loginTargetName, password }),
    });
    if (!res.ok) {
        loginError.textContent = await apiErrorMessage(res, "Nome ou senha incorretos.");
        loginError.hidden = false;
        return;
    }
    currentUser = await res.json();
    clearCsrfToken();
    await ensureCsrfToken();
    closeLoginModal();
    await afterLogin();
});

function openNewProfileModal() {
    newProfileNameInput.value = "";
    newProfilePasswordInput.value = "";
    newProfileError.hidden = true;
    newProfileModal.hidden = false;
    newProfileNameInput.focus();
}
function closeNewProfileModal() {
    newProfileModal.hidden = true;
}
newProfileBtn.addEventListener("click", openNewProfileModal);
newProfileCancelBtn.addEventListener("click", closeNewProfileModal);
newProfileModal.addEventListener("click", (e) => {
    if (e.target === newProfileModal) closeNewProfileModal();
});
newProfileNameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        newProfilePasswordInput.focus();
    }
});
newProfilePasswordInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        newProfileSubmitBtn.click();
    }
});
newProfileSubmitBtn.addEventListener("click", async () => {
    const name = newProfileNameInput.value.trim();
    const password = newProfilePasswordInput.value;
    if (!name) {
        newProfileError.textContent = "Digite um nome.";
        newProfileError.hidden = false;
        return;
    }
    if (!password) {
        newProfileError.textContent = "Escolha uma senha.";
        newProfileError.hidden = false;
        return;
    }
    const res = await securityFetch("/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, password }),
    });
    if (!res.ok) {
        newProfileError.textContent = await apiErrorMessage(res, "Não foi possível criar o perfil.");
        newProfileError.hidden = false;
        return;
    }
    currentUser = await res.json();
    clearCsrfToken();
    await ensureCsrfToken();
    closeNewProfileModal();
    await afterLogin();
});

logoutBtn.addEventListener("click", async () => {
    if (currentDocId) {
        await saveProgress();
        await closeSession();
    }
    stopTtsForLifecycle();
    engine.pause();
    await securityFetch("/logout", { method: "POST" });
    clearCsrfToken();
    currentUser = null;
    showLogin();
});

async function bootstrap() {
    try {
        const res = await fetch("/me");
        if (res.ok) {
            currentUser = await res.json();
            await afterLogin();
            return;
        }
    } catch {
        // Network hiccup — fall through to the login screen either way.
    }
    showLogin();
}

// ---- Reading mode (Foco / Fluxo) ----
// The motor (rsvp.js) has no concept of mode — it just advances a pointer
// and emits events. Mode only decides which region renders that pointer.
let activeMode = "focus";
let currentDocId = null;
let readerRequestId = 0;
const ttsDriver = new TTSDriver();
let ttsEnabled = false;
let ttsVoicesLoaded = false;
let ttsVoicesRequestId = 0;
let ttsWasPlaying = false;
let ttsStatusTimer = null;
let latestTtsWpm = null;

const FONT_RANGES = {
    focus: { min: 24, max: 96, step: 2 },
    flow: { min: 14, max: 28, step: 1 },
};

function applyFontSliderRange() {
    const r = FONT_RANGES[activeMode];
    fontSlider.min = r.min;
    fontSlider.max = r.max;
    fontSlider.step = r.step;
}

function loadModeSliders() {
    const wpmVal = getSetting(modeKey("wpm"));
    wpmSlider.value = wpmVal;
    wpmValue.textContent = wpmSlider.value;
    engine.setWpm(Number(wpmVal));

    const chunkVal = getSetting(modeKey("chunk"));
    chunkSlider.value = chunkVal;
    chunkValue.textContent = chunkSlider.value;
    engine.setChunkSize(ttsEnabled ? 1 : Number(chunkVal));

    const fontVal = getSetting(modeKey("font"));
    fontSlider.value = fontVal;
    fontValue.textContent = fontSlider.value;
    if (activeMode === "flow") {
        flowContent.style.fontSize = `${fontVal}px`;
    }
}

function updateOrpVisibility() {
    orpRow.hidden = activeMode !== "focus";
}
function updateSnapBackVisibility() {
    navSnapBackRow.hidden = activeMode !== "flow";
}

function applyModeUI(mode) {
    modeFocusBtn.classList.toggle("active", mode === "focus");
    modeFlowBtn.classList.toggle("active", mode === "flow");
    rsvpStage.hidden = mode !== "focus";
    flowRegion.hidden = mode !== "flow";
}

// ---- Wake Lock (keep the screen on while reading hands-free) ----
let wakeLock = null;
let wakeLockPending = false;
let wakeLockGeneration = 0;

async function acquireWakeLock() {
    if (!("wakeLock" in navigator) || wakeLock || wakeLockPending) return;
    const generation = wakeLockGeneration;
    wakeLockPending = true;
    try {
        const requestedLock = await navigator.wakeLock.request("screen");
        if (generation !== wakeLockGeneration || (!engine.playing && !ttsDriver.isPlaying())) {
            await requestedLock.release();
            return;
        }
        wakeLock = requestedLock;
        requestedLock.addEventListener("release", () => {
            if (wakeLock === requestedLock) wakeLock = null;
        });
    } catch (err) {
        wakeLock = null;
    } finally {
        wakeLockPending = false;
    }
}

function releaseWakeLock() {
    wakeLockGeneration += 1;
    if (wakeLock) {
        wakeLock.release().catch(() => {});
        wakeLock = null;
    }
}

document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && (engine.playing || ttsDriver.isPlaying()) && !wakeLock) {
        acquireWakeLock();
    }
    // Minimizar/trocar de app no celular não dispara pause explícito — este
    // é o gatilho mais confiável em mobile (beforeunload é inconsistente,
    // especialmente no iOS). Não fecha a sessão: só uma pausa, não o fim.
    if (document.visibilityState === "hidden" && !readerView.hidden) {
        saveProgress();
    }
});

// ---- Shrink-to-fit (long words/URLs must not wrap — that moves the eye,
// which is exactly what RSVP's fixed position is supposed to prevent) ----
// An off-screen probe measures the chunk's *intrinsic* text width. Measuring
// rsvpDisplay directly breaks under ORP: the ORP layout stretches the element
// to width:100% (to anchor the pivot), so its own scrollWidth always looks
// "too wide" and every word would shrink to the minimum.
const measureProbe = document.createElement("span");
measureProbe.setAttribute("aria-hidden", "true");
measureProbe.style.cssText =
    "position:absolute; left:-9999px; top:-9999px; white-space:nowrap; visibility:hidden;";
document.body.appendChild(measureProbe);

let lastChunkText = "";

function fitDisplayText(text = lastChunkText) {
    lastChunkText = text;
    const baseSize = Number(fontSlider.value) || 48;
    const minSize = Math.max(18, Math.floor(baseSize * 0.35));
    const available = rsvpStage.clientWidth - 32;
    const cs = getComputedStyle(rsvpDisplay);
    measureProbe.style.fontFamily = cs.fontFamily;
    measureProbe.style.fontWeight = cs.fontWeight;
    measureProbe.style.letterSpacing = cs.letterSpacing;
    measureProbe.textContent = text;
    let size = baseSize;
    measureProbe.style.fontSize = `${size}px`;
    while (measureProbe.offsetWidth > available && size > minSize) {
        size -= 2;
        measureProbe.style.fontSize = `${size}px`;
    }
    rsvpDisplay.style.fontSize = `${size}px`;
}

// ---- ORP (Optimal Recognition Point) — Focus only ----
let orpEnabled = getSetting("orpEnabled");

function applyOrpToggleUI() {
    orpToggle.textContent = orpEnabled ? "Ligado" : "Desligado";
    orpToggle.classList.toggle("active", orpEnabled);
}
applyOrpToggleUI();

orpToggle.addEventListener("click", () => {
    orpEnabled = !orpEnabled;
    setSetting("orpEnabled", orpEnabled);
    applyOrpToggleUI();
    engine.rerender();
});

// ---- Flow behavior toggles (both default off) ----
let navSnapBackOnClick = getSetting("navSnapBackOnClick");
let navPauseOnSwitch = getSetting("navPauseOnSwitch");

function applyNavToggleUI() {
    navSnapBackToggle.textContent = navSnapBackOnClick ? "Ligado" : "Desligado";
    navSnapBackToggle.classList.toggle("active", navSnapBackOnClick);
    navPauseSwitchToggle.textContent = navPauseOnSwitch ? "Ligado" : "Desligado";
    navPauseSwitchToggle.classList.toggle("active", navPauseOnSwitch);
}
applyNavToggleUI();

navSnapBackToggle.addEventListener("click", () => {
    navSnapBackOnClick = !navSnapBackOnClick;
    setSetting("navSnapBackOnClick", navSnapBackOnClick);
    applyNavToggleUI();
});
navPauseSwitchToggle.addEventListener("click", () => {
    navPauseOnSwitch = !navPauseOnSwitch;
    setSetting("navPauseOnSwitch", navPauseOnSwitch);
    applyNavToggleUI();
});

function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function splitOrp(word) {
    const idx = computeOrpIndex(word);
    return {
        before: word.slice(0, idx),
        pivot: word.slice(idx, idx + 1),
        after: word.slice(idx + 1),
    };
}

function renderChunk(tokens) {
    rsvpDisplay.classList.remove("orp-single");
    if (!orpEnabled) {
        rsvpDisplay.textContent = tokens.map((t) => t.text).join(" ");
        return;
    }
    if (tokens.length === 1) {
        rsvpDisplay.classList.add("orp-single");
        const { before, pivot, after } = splitOrp(tokens[0].text);
        rsvpDisplay.innerHTML =
            `<span class="orp-before">${escapeHtml(before)}</span>` +
            `<span class="orp-pivot">${escapeHtml(pivot)}</span>` +
            `<span class="orp-after">${escapeHtml(after)}</span>`;
        return;
    }
    rsvpDisplay.innerHTML = tokens
        .map((t) => {
            const { before, pivot, after } = splitOrp(t.text);
            return `${escapeHtml(before)}<span class="orp-pivot">${escapeHtml(pivot)}</span>${escapeHtml(after)}`;
        })
        .join(" ");
}

// ---- Flow content (full text, click-to-jump) ----
// Built once per document and cached — switching modes back and forth
// doesn't rebuild the DOM. One click listener on the container (event
// delegation) instead of one per word, since a document can have tens of
// thousands of tokens.
//
// Lazy spanification (Fase 6.1): building a <span> per word up-front froze
// the tab for ~7s on a 146k-word book. Instead each paragraph starts as
// plain text (a <div> with a text node — near-instant to build for the
// whole document, so native scroll height and Ctrl+F work immediately) and
// only becomes per-word <span>s when it's near the viewport (spanified on
// scroll) or when the reading highlight needs a word inside it (force-spanify).
//
// Trigger is a throttled scroll handler with a binary search on offsetTop —
// not IntersectionObserver. IO is the "textbook" choice but its async
// intersection callback doesn't fire at all in the headless test browser,
// so it couldn't be verified live; the scroll+offsetTop approach reaches the
// exact same end state (lazy, no freeze, native scroll/Ctrl+F intact) and is
// verifiable. offsetTop is monotonic across paragraphs (they stack in order),
// which is what makes the binary search valid — and .flow-content is
// position:relative so offsetTop shares scrollTop's coordinate space.
let flowBuiltForTokens = null;
let flowBlocks = []; // [{ el, startIdx, spanified }] — startIdx = global token index of the block's 1st word
let flowFollowMode = true;
let flowAutoScrolling = false;
let flowAutoScrollTimer = null;
let flowHighlightedEls = [];
let flowSpanifyFrameId = null;
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Hardening (Fase 6.1 audit): a "block" is NOT an unbounded paragraph. A
// pathological document (e.g. a PDF extracted as one break-less wall of text)
// would otherwise be a single block, and spanifying it would freeze the thread
// — the exact bug lazy spanification exists to kill. So a block closes at a
// paragraph end, OR once it is long enough and hits a sentence end (a natural
// break), OR at a hard ceiling regardless. Sentence-end breaks make the soft
// splits read like real paragraph breaks. Normal prose paragraphs (< 200
// words) never split, so nothing changes visually for them.
const FLOW_BLOCK_SENTENCE_TARGET = 200; // past this many tokens, break at the next sentence end
const FLOW_BLOCK_MAX_TOKENS = 250; // force a break here even mid-sentence

function blockPlainText(tokens, startIdx, endIdx) {
    let text = "";
    for (let i = startIdx; i < endIdx; i++) {
        text += (i > startIdx ? " " : "") + tokens[i].text;
    }
    return text;
}

// Replaces a block's plain text with one <span class="flow-word"> per word
// (idempotent — scroll-spanify and force-spanify can both target the same
// block). Builds into a DocumentFragment and appends ONCE: a single DOM
// mutation instead of 2·N interleaved appends, so spanifying a block never
// thrashes layout mid-loop. dataset.idx carries the GLOBAL token index so
// click and highlight can address any word regardless of which block it's in.
function spanifyBlock(bIdx) {
    const blk = flowBlocks[bIdx];
    if (!blk || blk.spanified) return;
    const tokens = engine.getTokens();
    const endIdx = bIdx + 1 < flowBlocks.length ? flowBlocks[bIdx + 1].startIdx : tokens.length;
    const frag = document.createDocumentFragment();
    for (let i = blk.startIdx; i < endIdx; i++) {
        const span = document.createElement("span");
        span.className = "flow-word";
        span.textContent = tokens[i].text;
        span.dataset.idx = i;
        frag.appendChild(span);
        frag.appendChild(document.createTextNode(" "));
    }
    blk.el.replaceChildren(frag);
    blk.spanified = true;
}

// Binary search: which block owns a given global token index.
function blockIndexForToken(tokenIdx) {
    let lo = 0;
    let hi = flowBlocks.length - 1;
    let result = 0;
    while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (flowBlocks[mid].startIdx <= tokenIdx) {
            result = mid;
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return result;
}

// Spanifies every block within one viewport-height above/below the visible
// area. Split into a READ phase (measure offsetTop, collect targets — no
// mutation) and a WRITE phase (spanify) so reads and writes never interleave;
// interleaving them is what thrashes layout on mobile. offsetTop is monotonic
// across blocks (they stack in order), which makes the binary search valid,
// and .flow-content is position:relative so offsetTop shares scrollTop's
// coordinate space.
function measureVisibleFlowBlockIndexes() {
    if (!flowBlocks.length) return;
    const view = flowContent.clientHeight;
    const scrollTop = flowContent.scrollTop;
    const top = scrollTop - view; // one screen of pre-spanify buffer
    const bottom = scrollTop + view * 2;

    let lo = 0;
    let hi = flowBlocks.length - 1;
    let startP = flowBlocks.length;
    while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (flowBlocks[mid].el.offsetTop >= top) {
            startP = mid;
            hi = mid - 1;
        } else {
            lo = mid + 1;
        }
    }
    const targets = [];
    for (let i = Math.max(0, startP - 1); i < flowBlocks.length; i++) {
        if (flowBlocks[i].el.offsetTop > bottom) break;
        if (!flowBlocks[i].spanified) targets.push(i);
    }
    return targets;
}

function spanifyFlowBlocks(blockIndexes) {
    for (const i of blockIndexes) spanifyBlock(i);
}

function spanifyVisibleBlocks() {
    // Keep the phases structurally separate: this function completes every
    // layout read before spanifyFlowBlocks performs the first live-DOM write.
    const targets = measureVisibleFlowBlockIndexes();
    if (!targets || targets.length === 0) return;
    spanifyFlowBlocks(targets);
}

// Coalesce a burst of scroll events into one spanify pass per animation
// frame. Raw scroll events fire faster than the browser paints, so measuring
// layout on each one is wasted work; batching to rAF also means the read
// happens after layout has settled for the frame, not mid-scroll.
function scheduleSpanifyPass() {
    if (flowSpanifyFrameId !== null || readerView.hidden || flowRegion.hidden || !flowBlocks.length) return;
    const scheduledForTokens = flowBuiltForTokens;
    flowSpanifyFrameId = requestAnimationFrame(() => {
        flowSpanifyFrameId = null;
        // A navigation/reset may have happened after this frame was queued.
        // Never let obsolete work mutate the next document's Flow DOM.
        if (readerView.hidden || flowRegion.hidden || flowBuiltForTokens !== scheduledForTokens) return;
        spanifyVisibleBlocks();
    });
}

function buildFlowContent(tokens) {
    if (flowBuiltForTokens === tokens) return;
    flowBlocks = [];

    const frag = document.createDocumentFragment();
    let blockStart = 0;
    let count = 0;
    const flushBlock = (endIdx) => {
        const el = document.createElement("div");
        el.className = "flow-paragraph";
        el.textContent = blockPlainText(tokens, blockStart, endIdx);
        frag.appendChild(el);
        flowBlocks.push({ el, startIdx: blockStart, spanified: false });
        blockStart = endIdx;
        count = 0;
    };
    tokens.forEach((token, idx) => {
        count++;
        const sentenceBreak = count >= FLOW_BLOCK_SENTENCE_TARGET && token.sentenceEnd;
        if (token.paragraphEnd || sentenceBreak || count >= FLOW_BLOCK_MAX_TOKENS) {
            flushBlock(idx + 1);
        }
    });
    if (blockStart < tokens.length || flowBlocks.length === 0) {
        flushBlock(tokens.length);
    }
    flowContent.replaceChildren(frag);

    flowBuiltForTokens = tokens;
    flowHighlightedEls = [];
    // Reading offsetTop below forces the layout the spanify pass needs, so a
    // direct synchronous call is both correct and cheaper than deferring.
    spanifyVisibleBlocks(); // spanify whatever's on screen at the initial (top) position
}

function ensureFlowBuilt() {
    const tokens = engine.getTokens();
    if (!tokens.length) return;
    buildFlowContent(tokens);
}

// Full reset of Flow's cached DOM/state — called when a new document loads so
// the previous document's spans, scroll position and follow state don't leak
// into the next one (all this state is module-level and would otherwise
// persist across documents).
function resetFlowState() {
    flowBuiltForTokens = null;
    flowBlocks = [];
    flowHighlightedEls = [];
    flowFollowMode = true;
    flowAutoScrolling = false;
    if (flowSpanifyFrameId !== null) {
        cancelAnimationFrame(flowSpanifyFrameId);
        flowSpanifyFrameId = null;
    }
    clearTimeout(flowAutoScrollTimer);
    flowAutoScrollTimer = null;
    flowContent.replaceChildren();
    flowContent.scrollTop = 0;
    flowBackToPositionBtn.hidden = true;
}

function buildParagraphMarks(tokens) {
    paragraphMarks.innerHTML = "";
    const total = tokens.length;
    if (!total) return;
    const frag = document.createDocumentFragment();
    tokens.forEach((token, idx) => {
        if (token.paragraphEnd) {
            const mark = document.createElement("span");
            mark.style.left = `${((idx + 1) / total) * 100}%`;
            frag.appendChild(mark);
        }
    });
    paragraphMarks.appendChild(frag);
}

function scrollFlowToCurrentWord(behavior) {
    const el = flowHighlightedEls[0];
    if (!el) return;
    flowAutoScrolling = true;
    el.scrollIntoView({ block: "center", behavior: prefersReducedMotion ? "auto" : behavior });
    clearTimeout(flowAutoScrollTimer);
    flowAutoScrollTimer = setTimeout(() => {
        flowAutoScrolling = false;
        flowAutoScrollTimer = null;
    }, 200);
}

// Resolves a global token index to its <span>, force-spanifying that
// paragraph if the reader reached it before it scrolled into view (e.g. a
// TOC jump or a restored position deep in the book). Returns null only if
// the index is out of range.
function flowWordEl(tokenIdx) {
    const total = engine.getTokens().length;
    if (tokenIdx < 0 || tokenIdx >= total || !flowBlocks.length) return null;
    const bIdx = blockIndexForToken(tokenIdx);
    spanifyBlock(bIdx);
    // .children is element-only (the " " separators are text nodes, so they
    // don't shift the index) — child[k] is the k-th word of the block.
    return flowBlocks[bIdx].el.children[tokenIdx - flowBlocks[bIdx].startIdx] || null;
}

// Highlights the *whole* chunk currently on screen (all N words when
// "palavras por vez" > 1), not just its first word — so Flow matches what
// Focus is actually flashing instead of looking like it skipped words.
function updateFlowHighlight(chunkTokens) {
    if (flowRegion.hidden || !flowBlocks.length) return;
    const start = engine.pointer;
    const count = chunkTokens ? chunkTokens.length : 1;
    flowHighlightedEls.forEach((el) => el.classList.remove("flow-current"));
    flowHighlightedEls = [];
    for (let i = start; i < start + count; i++) {
        const el = flowWordEl(i);
        if (el) {
            el.classList.add("flow-current");
            flowHighlightedEls.push(el);
        }
    }
    if (flowFollowMode && flowHighlightedEls.length) {
        scrollFlowToCurrentWord("auto");
    }
}

flowContent.addEventListener("scroll", () => {
    if (!flowBlocks.length || readerView.hidden || flowRegion.hidden) return;
    // Runs for every scroll (user or auto-follow) — new blocks entering the
    // viewport need spanifying either way, coalesced to one pass per frame
    // (see scheduleSpanifyPass) so bursts of scroll events don't thrash.
    scheduleSpanifyPass();
    if (flowAutoScrolling) return;
    if (flowFollowMode) {
        flowFollowMode = false;
        flowBackToPositionBtn.hidden = false;
    }
});

flowBackToPositionBtn.addEventListener("click", () => {
    flowFollowMode = true;
    flowBackToPositionBtn.hidden = true;
    scrollFlowToCurrentWord("smooth");
});

flowContent.addEventListener("click", (e) => {
    const wordEl = e.target.closest(".flow-word");
    if (!wordEl) return;
    navigateToToken(Number(wordEl.dataset.idx));
    if (navSnapBackOnClick) {
        modeFocusBtn.click();
    }
});

function updateLiveCounter(pointer, total) {
    if (!total) {
        readingProgressInfo.textContent = "";
        return;
    }
    const remaining = Math.max(0, total - pointer);
    if (ttsEnabled) {
        const rate = Number(ttsRateSlider.value) || 1;
        const wpmLabel = Number.isFinite(latestTtsWpm)
            ? ` · ≈ ${Math.round(latestTtsWpm).toLocaleString()} WPM`
            : "";
        readingProgressInfo.textContent =
            `${pointer.toLocaleString()} / ${total.toLocaleString()} palavras · ` +
            `Narrador ${rate.toFixed(1)}x${wpmLabel}`;
        return;
    }
    const wpm = Number(wpmSlider.value) || 300;
    const minutesLeft = Math.max(0, Math.round(remaining / wpm));
    readingProgressInfo.textContent =
        `${pointer.toLocaleString()} / ${total.toLocaleString()} palavras · ` +
        `~${minutesLeft} min restantes`;
}

// ---- RSVP engine wiring ----
// activeMode decides which region a chunk render goes to; the motor itself
// never needs to know. Reading activeMode fresh on every call (not captured)
// means a mode switch takes effect on the very next tick without any extra
// wiring.
const engine = new RSVPEngine({
    onChunk: (tokens) => {
        if (activeMode === "focus") {
            const plain = tokens.map((t) => t.text).join(" ");
            renderChunk(tokens);
            fitDisplayText(plain);
        } else {
            updateFlowHighlight(tokens);
        }
    },
    onProgress: (fraction, pointer, total) => {
        progressFill.style.width = `${Math.min(100, fraction * 100)}%`;
        updateLiveCounter(pointer, total);
    },
    onEnd: () => {
        refreshPlayButton();
        if (activeMode === "focus") {
            rsvpDisplay.classList.remove("orp-single");
            rsvpDisplay.textContent = "Fim";
            fitDisplayText("Fim");
        }
        progressFill.style.width = "100%";
        // Fim de documento é sinal inequívoco no RSVP — marca 'lido'
        // automaticamente (reversível a qualquer momento na biblioteca).
        saveProgress({ status: "lido" });
        closeSession();
    },
});

function showTtsStatus(message, { error = false, timeout = 0 } = {}) {
    clearTimeout(ttsStatusTimer);
    ttsStatusTimer = null;
    ttsStatus.textContent = message || "";
    ttsStatus.classList.toggle("error", error);
    ttsStatus.hidden = !message;
    if (message && timeout > 0) {
        ttsStatusTimer = setTimeout(() => {
            ttsStatus.hidden = true;
            ttsStatusTimer = null;
        }, timeout);
    }
}

function buildVoiceGroups(voices) {
    const groups = new Map();
    voices.forEach((voice) => {
        const metadata = describeVoice(voice);
        if (!groups.has(metadata.locale)) {
            groups.set(metadata.locale, { order: metadata.order, voices: [] });
        }
        groups.get(metadata.locale).voices.push(metadata);
    });
    return [...groups.entries()]
        .sort(([, left], [, right]) => left.order - right.order)
        .map(([locale, group]) => {
            const optgroup = document.createElement("optgroup");
            optgroup.label = locale;
            group.voices
                .sort((left, right) => left.name.localeCompare(right.name, "pt-BR"))
                .forEach((metadata) => {
                    const option = document.createElement("option");
                    option.value = metadata.id;
                    option.textContent = metadata.label;
                    if (metadata.lang) option.lang = metadata.lang;
                    optgroup.appendChild(option);
                });
            return optgroup;
        });
}

async function loadTtsVoices() {
    if (ttsVoicesLoaded) return;
    const requestId = ++ttsVoicesRequestId;
    try {
        const res = await apiFetch("/tts/voices");
        if (requestId !== ttsVoicesRequestId || !currentUser) return;
        if (!res.ok) return;
        const data = await res.json();
        if (requestId !== ttsVoicesRequestId || !currentUser) return;
        const voices = Array.isArray(data.voices) ? data.voices : [];
        const serverDefault = data.default || "pf_dora";
        const stored = getSetting("ttsVoice") || serverDefault;
        const selected = voices.length === 0
            ? stored
            : voices.includes(stored)
                ? stored
                : voices.includes(serverDefault) ? serverDefault : voices[0];
        const options = voices.length ? voices : [selected || serverDefault];
        ttsVoice.replaceChildren(...buildVoiceGroups(options));
        ttsVoice.value = selected || serverDefault;
        setSetting("ttsVoice", ttsVoice.value);
        if (currentDocId) {
            const resume = ttsDriver.isPlaying();
            ttsDriver.setVoice(ttsVoice.value);
            if (ttsEnabled && resume) await ttsDriver.play();
        }
        ttsVoicesLoaded = true;
    } catch {
        // The default voice remains usable; generation will surface a precise
        // error if Kokoro itself is unavailable when the user presses play.
    }
}

function applyTtsUi() {
    ttsToggle.classList.toggle("active", ttsEnabled);
    ttsToggle.setAttribute("aria-pressed", String(ttsEnabled));
    ttsToggleLabel.textContent = ttsEnabled ? "Narrador ativo" : "Ativar Narrador";
    ttsSettings.hidden = !ttsEnabled;
    wpmRow.hidden = ttsEnabled;
    chunkRow.hidden = ttsEnabled;
}

function handleTtsStateChange({ playing, loading }) {
    refreshPlayButton();
    if (!ttsWasPlaying && playing) {
        openSessionIfNeeded();
    } else if (ttsWasPlaying && !playing && !loading) {
        saveProgress();
    }
    ttsWasPlaying = playing;
}

function handleTtsEnd() {
    refreshPlayButton();
    if (activeMode === "focus") {
        rsvpDisplay.classList.remove("orp-single");
        rsvpDisplay.textContent = "Fim";
        fitDisplayText("Fim");
    }
    progressFill.style.width = "100%";
    saveProgress({ status: "lido" });
    closeSession();
}

function handleTtsMetricsChange({ rate, effectiveWpm }) {
    const safeRate = Math.max(0.5, Math.min(4, Number(rate) || 1));
    ttsRateValue.textContent = `${safeRate.toFixed(1)}x`;
    latestTtsWpm = Number.isFinite(effectiveWpm) ? effectiveWpm : null;
    ttsEffectiveWpm.textContent = latestTtsWpm === null
        ? "—"
        : Math.round(latestTtsWpm).toLocaleString();
    updateLiveCounter(engine.pointer, engine.getTokens().length);
}

function handleTtsBufferChange({ readySeconds, targetSeconds, blocks }) {
    const ready = Math.max(0, Math.round(Number(readySeconds) || 0));
    const target = Math.max(30, Math.round(Number(targetSeconds) || 60));
    ttsBufferValue.textContent = `${target}s`;
    ttsBufferStatus.textContent = blocks > 0
        ? `${ready}s prontos em ${blocks} ${blocks === 1 ? "bloco" : "blocos"}`
        : "Preparado sob demanda";
}

function configureTtsForDocument(documentId) {
    ttsDriver.configure({
        engine,
        apiFetch,
        docId: documentId,
        voice: ttsVoice.value || getSetting("ttsVoice") || "pf_dora",
        onError: (message) => showTtsStatus(message, { error: true }),
        onEnd: handleTtsEnd,
        onStateChange: handleTtsStateChange,
        onMetricsChange: handleTtsMetricsChange,
        onBufferChange: handleTtsBufferChange,
        onBlockChange: (block) => {
            if (block.timing_fallback) {
                showTtsStatus("Áudio mantido com sincronização aproximada neste trecho.");
            } else {
                showTtsStatus("");
            }
        },
    });
    ttsDriver.setRate(Number(ttsRateSlider.value));
    ttsDriver.setBufferSeconds(Number(ttsBufferSlider.value));
}

function setTtsEnabled(enabled) {
    if (enabled === ttsEnabled) return;
    if (enabled) {
        engine.pause();
        ttsEnabled = true;
        engine.setChunkSize(1);
        engine.rerender();
        ttsDriver.setVoice(ttsVoice.value || "pf_dora");
        ttsDriver.setRate(Number(ttsRateSlider.value));
        ttsDriver.setBufferSeconds(Number(ttsBufferSlider.value));
        showTtsStatus("");
    } else {
        ttsEnabled = false;
        ttsDriver.stop();
        ttsWasPlaying = false;
        engine.setChunkSize(Number(getSetting(modeKey("chunk"))) || 1);
        engine.rerender();
        saveProgress();
        showTtsStatus("");
    }
    applyTtsUi();
    refreshPlayButton();
}

function stopTtsForLifecycle() {
    ttsEnabled = false;
    ttsDriver.reset();
    ttsWasPlaying = false;
    latestTtsWpm = null;
    ttsEffectiveWpm.textContent = "—";
    ttsBufferStatus.textContent = "Preparado sob demanda";
    clearTimeout(ttsStatusTimer);
    ttsStatusTimer = null;
    showTtsStatus("");
    applyTtsUi();
    engine.setChunkSize(Number(getSetting(modeKey("chunk"))) || 1);
}

function refreshPlayButton() {
    const playing = ttsEnabled ? ttsDriver.isPlaying() : engine.playing;
    const loading = ttsEnabled && ttsDriver.isLoading();
    playPauseBtn.textContent = playing ? "⏸" : "▶";
    playPauseBtn.classList.toggle("is-loading", loading);
    playPauseBtn.setAttribute("aria-busy", String(loading));
    playPauseBtn.setAttribute("aria-label", loading ? "Carregando narração" : playing ? "Pausar" : "Reproduzir");
    if (engine.playing || ttsDriver.isPlaying()) {
        acquireWakeLock();
    } else {
        releaseWakeLock();
    }
}

async function doTogglePlay(btn) {
    if (ttsEnabled) {
        engine.pause();
        await ttsDriver.toggle();
        if (btn) btn.blur();
        return;
    }
    const wasPlaying = engine.playing;
    engine.toggle();
    refreshPlayButton();
    if (!wasPlaying && engine.playing) {
        openSessionIfNeeded();
    } else if (wasPlaying && !engine.playing) {
        saveProgress();
    }
    if (btn) btn.blur();
}

function sentenceStart(tokens, fromIndex) {
    let idx = fromIndex;
    while (idx > 0 && !tokens[idx - 1].sentenceEnd) idx -= 1;
    return idx;
}

function rewindTarget() {
    const tokens = engine.getTokens();
    if (!tokens.length) return 0;
    const currentStart = sentenceStart(tokens, engine.pointer);
    return currentStart < engine.pointer
        ? currentStart
        : currentStart > 0 ? sentenceStart(tokens, currentStart - 1) : 0;
}

function forwardTarget() {
    const tokens = engine.getTokens();
    if (!tokens.length) return 0;
    let idx = Math.max(0, Math.min(tokens.length - 1, engine.pointer));
    while (idx < tokens.length - 1 && !tokens[idx].sentenceEnd) idx += 1;
    return Math.min(tokens.length - 1, idx + 1);
}

async function navigateToToken(tokenIdx) {
    const total = engine.getTokens().length;
    if (!total) return;
    const target = Math.max(0, Math.min(total - 1, Math.floor(tokenIdx)));
    if (ttsEnabled) {
        await ttsDriver.seek(target);
    } else {
        engine.seekToIndex(target);
    }
    refreshPlayButton();
}

async function doRewind(btn) {
    await navigateToToken(rewindTarget());
    saveProgress();
    if (btn) btn.blur();
}

async function doForward(btn) {
    await navigateToToken(forwardTarget());
    saveProgress();
    if (btn) btn.blur();
}

playPauseBtn.addEventListener("click", () => doTogglePlay(playPauseBtn));
rewindBtn.addEventListener("click", () => doRewind(rewindBtn));
forwardBtn.addEventListener("click", () => doForward(forwardBtn));
rsvpStage.addEventListener("click", () => doTogglePlay());

const initialTtsRate = Math.max(0.5, Math.min(4, Number(getSetting("ttsRate")) || 1));
ttsRateSlider.value = initialTtsRate.toFixed(1);
ttsRateValue.textContent = `${initialTtsRate.toFixed(1)}x`;
const initialTtsBuffer = Math.max(
    30,
    Math.min(120, Math.round((Number(getSetting("ttsBufferSeconds")) || 60) / 15) * 15),
);
ttsBufferSlider.value = String(initialTtsBuffer);
ttsBufferValue.textContent = `${initialTtsBuffer}s`;
applyTtsUi();

ttsToggle.addEventListener("click", () => {
    setTtsEnabled(!ttsEnabled);
    ttsToggle.blur();
});

ttsVoice.addEventListener("change", async () => {
    const resume = ttsDriver.isPlaying();
    setSetting("ttsVoice", ttsVoice.value);
    ttsDriver.setVoice(ttsVoice.value);
    if (ttsEnabled && resume) await ttsDriver.play();
});

ttsRateSlider.addEventListener("input", () => {
    const rate = Math.max(0.5, Math.min(4, Number(ttsRateSlider.value) || 1));
    ttsRateValue.textContent = `${rate.toFixed(1)}x`;
    setSetting("ttsRate", rate);
    ttsDriver.setRate(rate);
});

ttsBufferSlider.addEventListener("input", () => {
    const seconds = Math.max(30, Math.min(120, Number(ttsBufferSlider.value) || 60));
    ttsBufferValue.textContent = `${seconds}s`;
    setSetting("ttsBufferSeconds", seconds);
    ttsDriver.setBufferSeconds(seconds);
});

// ---- Mode switching ----
// Entering Flow pushes a history entry; the Foco button (and the Android
// back gesture) pop it via history.back() instead of pushing another entry
// — mirrors the library/reader back-button pattern already in this app.
function switchMode(mode, { push = true } = {}) {
    if (mode === activeMode) return;
    if (navPauseOnSwitch && (engine.playing || ttsDriver.isPlaying() || ttsDriver.isLoading())) {
        engine.pause();
        if (ttsEnabled) ttsDriver.pause();
    }
    saveProgress();
    activeMode = mode;
    setSetting("activeMode", mode);
    applyModeUI(mode);
    applyFontSliderRange();
    loadModeSliders();
    updateOrpVisibility();
    updateSnapBackVisibility();
    if (mode === "flow") {
        ensureFlowBuilt();
    }
    engine.rerender();
    refreshPlayButton();
    if (push) {
        history.pushState({ view: "reader", id: currentDocId, mode }, "", `#/read/${currentDocId}/${mode}`);
    }
}

modeFocusBtn.addEventListener("click", () => {
    if (activeMode === "flow") history.back();
});
modeFlowBtn.addEventListener("click", () => {
    if (activeMode === "focus") switchMode("flow", { push: true });
});

// ---- Scrubber (draggable progress bar) ----
function seekFromPointerEvent(e) {
    const rect = scrubber.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const fraction = rect.width ? x / rect.width : 0;
    const total = engine.getTokens().length;
    return navigateToToken(Math.floor(fraction * total));
}

let scrubbing = false;
let scrubSeekPromise = Promise.resolve();
scrubber.addEventListener("pointerdown", (e) => {
    scrubbing = true;
    scrubber.setPointerCapture(e.pointerId);
    scrubSeekPromise = seekFromPointerEvent(e);
});
scrubber.addEventListener("pointermove", (e) => {
    if (scrubbing) scrubSeekPromise = seekFromPointerEvent(e);
});
scrubber.addEventListener("pointerup", async () => {
    scrubbing = false;
    await scrubSeekPromise;
    saveProgress();
});
scrubber.addEventListener("pointercancel", async () => {
    scrubbing = false;
    await scrubSeekPromise;
    saveProgress();
});

wpmSlider.addEventListener("input", () => {
    engine.setWpm(Number(wpmSlider.value));
    wpmValue.textContent = wpmSlider.value;
    setSetting(modeKey("wpm"), wpmSlider.value);
});
chunkSlider.addEventListener("input", () => {
    engine.setChunkSize(Number(chunkSlider.value));
    chunkValue.textContent = chunkSlider.value;
    setSetting(modeKey("chunk"), chunkSlider.value);
});
fontSlider.addEventListener("input", () => {
    fontValue.textContent = fontSlider.value;
    setSetting(modeKey("font"), fontSlider.value);
    if (activeMode === "flow") {
        flowContent.style.fontSize = `${fontSlider.value}px`;
    } else {
        fitDisplayText();
    }
});

document.addEventListener("keydown", (e) => {
    if (readerView.hidden) return;
    if (e.code === "Space") {
        e.preventDefault();
        doTogglePlay();
    } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        doRewind();
    } else if (e.code === "ArrowRight") {
        e.preventDefault();
        doForward();
    } else if (e.code === "ArrowUp") {
        e.preventDefault();
        if (ttsEnabled) {
            ttsRateSlider.value = Math.min(4, Number(ttsRateSlider.value) + 0.1).toFixed(1);
            ttsRateSlider.dispatchEvent(new Event("input"));
        } else {
            wpmSlider.value = Math.min(1000, Number(wpmSlider.value) + 10);
            wpmSlider.dispatchEvent(new Event("input"));
        }
    } else if (e.code === "ArrowDown") {
        e.preventDefault();
        if (ttsEnabled) {
            ttsRateSlider.value = Math.max(0.5, Number(ttsRateSlider.value) - 0.1).toFixed(1);
            ttsRateSlider.dispatchEvent(new Event("input"));
        } else {
            wpmSlider.value = Math.max(100, Number(wpmSlider.value) - 10);
            wpmSlider.dispatchEvent(new Event("input"));
        }
    }
});

// ---- Progresso e sessões por usuário (Fase 5) ----
// currentSessionId != null enquanto uma sessão está aberta para o documento
// atual; nasce no primeiro play (não na abertura do documento) e é fechada
// ao sair do leitor ou ao terminar. O heartbeat roda a cada ~30s mas só
// efetivamente grava enquanto engine.playing — mantê-lo vivo mesmo pausado
// evita o custo de start/stop a cada toggle, o no-op é barato.
let currentSessionId = null;
let heartbeatTimer = null;

async function saveProgress(extraFields = {}) {
    if (!currentDocId) return;
    await apiFetch(`/documents/${currentDocId}/progress`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ position: engine.pointer, ...extraFields }),
    });
}

function startHeartbeatIfNeeded() {
    if (heartbeatTimer) return;
    heartbeatTimer = setInterval(sendHeartbeat, 30_000);
}

async function sendHeartbeat() {
    // In narrator mode the audio element is the clock and engine.playing is
    // intentionally false; either clock therefore keeps the session alive.
    if (!currentSessionId || (!engine.playing && !ttsDriver.isPlaying())) return;
    await apiFetch(`/sessions/${currentSessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ end_pointer: engine.pointer, position: engine.pointer }),
    });
}

async function openSessionIfNeeded() {
    if (currentSessionId !== null || !currentDocId) return;
    const res = await apiFetch("/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: currentDocId, mode: activeMode, start_pointer: engine.pointer }),
    });
    if (!res.ok) return;
    const data = await res.json();
    // session_id vem null quando collect_stats está desligado — opt-out
    // respeitado no momento de gravar, não só de listar.
    if (data.session_id != null) {
        currentSessionId = data.session_id;
        startHeartbeatIfNeeded();
    }
}

async function closeSession() {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
    if (!currentSessionId) return;
    const sessionId = currentSessionId;
    currentSessionId = null;
    const wpm = ttsEnabled ? null : Number(wpmSlider.value) || 300;
    await apiFetch(`/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            end_pointer: engine.pointer,
            position: engine.pointer,
            ended_at: true,
            avg_wpm: wpm,
        }),
    });
}

function resetSessionState() {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
    currentSessionId = null;
}

// ---- Statistics dashboard (Fase 9) ----
let statsScope = "me";
let statsRequestId = 0;
let statsAbortController = null;

function cancelStatsRequest() {
    statsRequestId += 1;
    if (statsAbortController) statsAbortController.abort();
    statsAbortController = null;
}

function formatStatNumber(value) {
    return new Intl.NumberFormat("pt-BR").format(value || 0);
}

function formatReadingTime(seconds) {
    const minutes = Math.round((seconds || 0) / 60);
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    const remainder = minutes % 60;
    return remainder ? `${hours}h ${remainder}min` : `${hours}h`;
}

function expandDailySeries(data) {
    const values = new Map(data.daily.map((point) => [point.date, point.words]));
    if (!data.daily.length && !data.period_days) return [];
    const end = new Date(`${data.generated_at.slice(0, 10)}T00:00:00Z`);
    let start;
    if (data.period_days) {
        start = new Date(end);
        start.setUTCDate(start.getUTCDate() - data.period_days + 1);
    } else {
        start = new Date(`${data.daily[0].date}T00:00:00Z`);
    }
    const series = [];
    for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
        const key = cursor.toISOString().slice(0, 10);
        series.push({ date: key, words: values.get(key) || 0 });
    }
    return series;
}

function renderDailyChart(data) {
    const series = expandDailySeries(data);
    statsDailyChart.textContent = "";
    statsChartEmpty.hidden = series.some((point) => point.words > 0);
    statsDailyChart.hidden = !statsChartEmpty.hidden;
    if (statsDailyChart.hidden) return;

    const ns = "http://www.w3.org/2000/svg";
    const width = 720;
    const height = 220;
    const plotTop = 16;
    const plotBottom = 190;
    const maxWords = Math.max(...series.map((point) => point.words), 1);
    [0, 0.5, 1].forEach((ratio) => {
        const y = plotBottom - ratio * (plotBottom - plotTop);
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", "44");
        line.setAttribute("x2", String(width - 8));
        line.setAttribute("y1", String(y));
        line.setAttribute("y2", String(y));
        line.setAttribute("class", "chart-grid");
        statsDailyChart.appendChild(line);

        const label = document.createElementNS(ns, "text");
        label.setAttribute("x", "38");
        label.setAttribute("y", String(y + 4));
        label.setAttribute("text-anchor", "end");
        label.setAttribute("class", "chart-label");
        label.textContent = formatStatNumber(Math.round(maxWords * ratio));
        statsDailyChart.appendChild(label);
    });

    const plotWidth = width - 56;
    const step = plotWidth / series.length;
    const barWidth = Math.max(0.8, step * 0.72);
    series.forEach((point, index) => {
        if (!point.words) return;
        const barHeight = Math.max(2, (point.words / maxWords) * (plotBottom - plotTop));
        const rect = document.createElementNS(ns, "rect");
        rect.setAttribute("x", String(44 + index * step + (step - barWidth) / 2));
        rect.setAttribute("y", String(plotBottom - barHeight));
        rect.setAttribute("width", String(barWidth));
        rect.setAttribute("height", String(barHeight));
        rect.setAttribute("rx", String(Math.min(2, barWidth / 2)));
        rect.setAttribute("class", "chart-bar");
        const title = document.createElementNS(ns, "title");
        title.textContent = `${point.date}: ${formatStatNumber(point.words)} palavras`;
        rect.appendChild(title);
        statsDailyChart.appendChild(rect);
    });
}

function renderStats(data) {
    const summary = data.summary;
    statsWords.textContent = formatStatNumber(summary.words);
    statsTime.textContent = formatReadingTime(summary.reading_seconds);
    statsWpm.textContent = summary.avg_wpm == null ? "--" : `${formatStatNumber(Math.round(summary.avg_wpm))} WPM`;
    statsStreak.textContent = `${summary.streak_days} ${summary.streak_days === 1 ? "dia" : "dias"}`;
    statsCompletion.textContent = `${summary.completion_rate.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
    statsSessions.textContent = formatStatNumber(summary.sessions);
    statsCollect.checked = data.collecting;
    statsChartCaption.textContent = data.period_days ? `ultimos ${data.period_days} dias` : "todo o historico";
    statsPrivacyNote.textContent = statsScope === "house"
        ? `${data.participants} participante(s). Apenas perfis com coleta ativa entram nos totais; titulos privados nunca aparecem.`
        : data.collecting
            ? "Suas sessoes estao sendo registradas. A conclusao considera todo o seu historico."
            : "A coleta esta pausada. Seu historico anterior continua visivel apenas para voce.";

    renderDailyChart(data);

    statsModes.textContent = "";
    const maxModeWords = Math.max(...data.modes.map((mode) => mode.words), 1);
    data.modes.forEach((mode) => {
        const row = document.createElement("div");
        row.className = "stats-mode-row";
        const name = document.createElement("strong");
        name.textContent = mode.mode === "focus" ? "Foco" : mode.mode === "flow" ? "Fluxo" : "Outro";
        const track = document.createElement("div");
        track.className = "stats-mode-track";
        const fill = document.createElement("div");
        fill.className = "stats-mode-fill";
        fill.style.width = `${Math.max(2, mode.words / maxModeWords * 100)}%`;
        track.appendChild(fill);
        const value = document.createElement("span");
        value.textContent = formatStatNumber(mode.words);
        row.append(name, track, value);
        statsModes.appendChild(row);
    });
    if (!data.modes.length) {
        const empty = document.createElement("p");
        empty.className = "empty-hint";
        empty.textContent = "Nenhum modo registrado.";
        statsModes.appendChild(empty);
    }

    statsDocuments.textContent = "";
    data.documents.forEach((doc) => {
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "stats-document-btn";
        const title = document.createElement("span");
        title.textContent = doc.title;
        const words = document.createElement("strong");
        words.textContent = formatStatNumber(doc.words);
        const detail = document.createElement("small");
        detail.textContent = `${formatReadingTime(doc.reading_seconds)} · ${doc.avg_wpm == null ? "sem WPM" : Math.round(doc.avg_wpm) + " WPM"}`;
        button.append(title, words, detail);
        button.addEventListener("click", () => showReader(doc.document_id));
        item.appendChild(button);
        statsDocuments.appendChild(item);
    });
    if (!data.documents.length) {
        const empty = document.createElement("li");
        empty.className = "empty-hint";
        empty.textContent = "Nenhum documento neste periodo.";
        statsDocuments.appendChild(empty);
    }
}

async function fetchStats() {
    cancelStatsRequest();
    const requestId = statsRequestId;
    statsAbortController = new AbortController();
    statsError.hidden = true;
    statsLoading.hidden = false;
    statsContent.setAttribute("aria-busy", "true");
    try {
        const res = await apiFetch(`/stats/dashboard?scope=${statsScope}&days=${statsPeriod.value}`, {
            signal: statsAbortController.signal,
        });
        if (requestId !== statsRequestId || res.status === 401) return;
        if (!res.ok) throw new Error(await apiErrorMessage(res, "Nao foi possivel carregar as estatisticas."));
        renderStats(await res.json());
    } catch (error) {
        if (error.name !== "AbortError" && requestId === statsRequestId) {
            statsError.textContent = error.message || "Nao foi possivel carregar as estatisticas.";
            statsError.hidden = false;
        }
    } finally {
        if (requestId === statsRequestId) {
            statsLoading.hidden = true;
            statsContent.removeAttribute("aria-busy");
            statsAbortController = null;
        }
    }
}

function showDashboard(push = true) {
    readerRequestId += 1;
    cancelLibraryRequest();
    if (currentDocId) {
        saveProgress();
        closeSession();
    }
    stopTtsForLifecycle();
    engine.pause();
    resetFlowState();
    currentDocId = null;
    loginView.hidden = true;
    libraryView.hidden = true;
    readerView.hidden = true;
    dashboardView.hidden = false;
    fetchStats();
    if (push) history.pushState({ view: "stats" }, "", "#/stats");
}

statsBtn.addEventListener("click", () => showDashboard());
dashboardBackBtn.addEventListener("click", () => history.back());
statsPeriod.addEventListener("change", fetchStats);
statsScopeButtons.forEach((button) => {
    button.addEventListener("click", () => {
        statsScope = button.dataset.statsScope;
        statsScopeButtons.forEach((candidate) => {
            const active = candidate === button;
            candidate.classList.toggle("active", active);
            candidate.setAttribute("aria-pressed", active ? "true" : "false");
        });
        fetchStats();
    });
});
statsCollect.addEventListener("change", async () => {
    const enabled = statsCollect.checked;
    statsCollect.disabled = true;
    const res = await apiFetch("/me/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collect_stats: enabled }),
    });
    if (res.ok) {
        localStorage.setItem(SETTINGS_PREFIX + "collectStats", enabled ? "1" : "0");
        await fetchStats();
    } else {
        statsCollect.checked = !enabled;
        statsError.textContent = await apiErrorMessage(res, "Nao foi possivel alterar a coleta.");
        statsError.hidden = false;
    }
    statsCollect.disabled = false;
});

// ---- Navigation ----
// Real history entries (pushState) so the Android back gesture/button moves
// reader → library instead of leaving the site, reloading inside the reader
// (or following a #/read/{id}/{mode} link) opens straight to that document
// and mode, and Fluxo→Foco→biblioteca pops one level at a time.
function showLibrary(push = true) {
    cancelStatsRequest();
    readerRequestId += 1;
    if (currentDocId) {
        saveProgress();
        closeSession();
    }
    stopTtsForLifecycle();
    engine.pause();
    resetFlowState();
    readerView.hidden = true;
    dashboardView.hidden = true;
    loginView.hidden = true;
    libraryView.hidden = false;
    currentDocId = null;
    fetchLibrary();
    if (push) history.pushState({ view: "library" }, "", "#/");
}

async function showReader(id, push = true, mode = "focus") {
    cancelStatsRequest();
    const requestId = ++readerRequestId;
    cancelLibraryRequest();
    // Trocar de documento direto (via popstate entre duas leituras, sem
    // passar pela biblioteca) precisa fechar a sessão/salvar a posição do
    // documento anterior antes de carregar o novo.
    if (currentDocId && currentDocId !== id) {
        saveProgress();
        closeSession();
    }
    stopTtsForLifecycle();
    const res = await apiFetch(`/documents/${id}`);
    if (requestId !== readerRequestId) return;
    if (!res.ok) {
        if (res.status !== 401) alert("Não foi possível carregar o documento.");
        return;
    }
    const doc = await res.json();
    currentDocId = id;
    resetSessionState();
    readerTitle.textContent = doc.title;
    closeTocDropdown();
    renderToc(doc.toc);
    // Reveal the reader view — and the correct mode region — *before*
    // loading. engine.load() renders the first chunk synchronously via
    // onChunk, and fitDisplayText() needs rsvp-stage to already have real
    // layout dimensions (a hidden element measures 0-width, which forced
    // every opening word to shrink to the minimum font size).
    libraryView.hidden = true;
    readerView.hidden = false;
    dashboardView.hidden = true;
    loginView.hidden = true;
    activeMode = mode;
    setSetting("activeMode", mode);
    applyModeUI(mode);
    applyFontSliderRange();
    loadModeSliders();
    updateOrpVisibility();
    updateSnapBackVisibility();

    resetFlowState(); // new document — clear Flow's cached spans, scroll and follow state
    engine.load(doc.raw_text);
    buildParagraphMarks(engine.getTokens());
    if (mode === "flow") {
        // load() already fired one render before Flow's spans existed for
        // these tokens (buildFlowContent needs the tokens engine.load() just
        // produced) — build now, then render again so the highlight lands.
        ensureFlowBuilt();
        engine.rerender();
    }
    configureTtsForDocument(id);
    refreshPlayButton();
    if (push) history.pushState({ view: "reader", id, mode }, "", `#/read/${id}/${mode}`);

    // Restaura a posição depois do load() (que sempre reseta o ponteiro pra
    // 0) — upsert lazy no servidor: cria a linha se não existir e promove
    // 'quero_ler' -> 'lendo' automaticamente, sem sobrescrever 'lido'/'abandonado'.
    const progressRes = await apiFetch(`/documents/${id}/progress`);
    if (requestId !== readerRequestId) return;
    if (progressRes.ok) {
        const progress = await progressRes.json();
        // O comentário histórico acima descrevia um upsert em GET. Desde R6,
        // a leitura é pura e a promoção é este PUT protegido por CSRF.
        if (progress.status === "quero_ler") {
            const promoted = await apiFetch(`/documents/${id}/progress`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: "lendo" }),
            });
            if (!promoted.ok || requestId !== readerRequestId) return;
        }
        if (requestId !== readerRequestId) return;
        // seekToIndex() já dispara _render() -> onChunk, que já sabe decidir
        // entre Foco/Fluxo — nenhuma chamada extra de highlight necessária.
        if (progress.position > 0) {
            engine.seekToIndex(progress.position);
        }
    }
}

window.addEventListener("popstate", (e) => {
    const state = e.state;
    if (state && state.view === "reader") {
        if (state.id === currentDocId) {
            switchMode(state.mode, { push: false });
        } else {
            showReader(state.id, false, state.mode || "focus");
        }
    } else if (state && state.view === "stats") {
        showDashboard(false);
    } else {
        showLibrary(false);
    }
});

function initFromLocation() {
    if (location.hash === "#/stats") {
        history.replaceState({ view: "stats" }, "", "#/stats");
        showDashboard(false);
        return;
    }
    const match = location.hash.match(/^#\/read\/(\d+)(?:\/(focus|flow))?$/);
    if (match) {
        const id = Number(match[1]);
        const mode = match[2] || "focus";
        history.replaceState({ view: "reader", id, mode }, "", `#/read/${id}/${mode}`);
        showReader(id, false, mode);
    } else {
        history.replaceState({ view: "library" }, "", "#/");
        showLibrary(false);
    }
}

backBtn.addEventListener("click", () => history.back());

// ---- Library ----
function estimatedMinutes(wordCount) {
    const wpm = getSetting("wpmFocus") || 300;
    return Math.max(1, Math.round(wordCount / wpm));
}

// Estado null (nunca aberto) mostra "— sem status —": placeholder só visual,
// nunca enviado via PUT — evita fingir que uma escolha já foi feita quando
// não existe linha em reading_progress ainda.
function openLibraryDocument(doc) {
    if (doc.progress_status === "abandonado") {
        openAbandonedModal(doc);
    } else {
        showReader(doc.id);
    }
}

function buildDocListItem(doc) {
    const manageable = canManage(doc);
    const pct = doc.word_count && doc.progress_position != null
        ? Math.min(100, Math.round((doc.progress_position / doc.word_count) * 100))
        : 0;

    const li = document.createElement("li");
    li.innerHTML = `
        <div class="doc-info">
            <div class="doc-title"></div>
            <div class="doc-meta"></div>
            <div class="doc-progress-bar" ${doc.progress_status ? "" : "hidden"}>
                <div class="doc-progress-fill" style="width: ${pct}%"></div>
            </div>
        </div>
        <div class="doc-actions">
            <select class="status-select" title="Status de leitura">
                ${doc.progress_status ? "" : '<option value="" selected disabled>— sem status —</option>'}
                <option value="quero_ler" ${doc.progress_status === "quero_ler" ? "selected" : ""}>⭐ Quero ler</option>
                <option value="lendo" ${doc.progress_status === "lendo" ? "selected" : ""}>🔖 Lendo</option>
                <option value="lido" ${doc.progress_status === "lido" ? "selected" : ""}>✅ Lido</option>
                <option value="abandonado" ${doc.progress_status === "abandonado" ? "selected" : ""}>🚫 Abandonado</option>
            </select>
            ${manageable ? '<button class="icon-btn rename-btn" title="Renomear">✏️</button><button class="icon-btn delete-btn" title="Excluir">🗑️</button>' : ""}
        </div>
    `;
    li.querySelector(".doc-title").textContent = doc.title;
    const privacyTag = doc.visibility === "private" ? " · 🔒 privado" : "";
    li.querySelector(".doc-meta").textContent =
        `${doc.format.toUpperCase()} · ${doc.word_count.toLocaleString()} palavras · ` +
        `~${estimatedMinutes(doc.word_count)} min · ${new Date(doc.created_at).toLocaleString()}${privacyTag}`;

    li.querySelector(".doc-info").addEventListener("click", () => openLibraryDocument(doc));

    li.querySelector(".status-select").addEventListener("change", async (e) => {
        e.stopPropagation();
        const newStatus = e.target.value;
        if (!newStatus) return;
        const previousStatus = doc.progress_status;
        // Keep click behavior correct while the PUT/refetch is still in flight:
        // marking as abandoned must protect the item immediately, in any shelf.
        doc.progress_status = newStatus;
        const res = await apiFetch(`/documents/${doc.id}/progress`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus }),
        });
        if (!res.ok) {
            doc.progress_status = previousStatus;
            if (res.status !== 401) fetchLibrary();
            return;
        }
        fetchLibrary();
    });

    if (manageable) {
        li.querySelector(".rename-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            openEditDocModal(doc);
        });
        li.querySelector(".delete-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            deleteDocument(doc);
        });
    }
    return li;
}

// ---- Fase 7: busca, coleções e prateleiras como filtro de primeira classe ----
// allFetchedDocs guarda a última resposta de /documents (já filtrada por
// busca no servidor); prateleira e coleção filtram em memória — instantâneo,
// sem round-trip extra, porque o resumo já vem com progress_status/collection.
let allFetchedDocs = [];
let currentShelf = "all";
let currentCollection = "";
let searchQuery = "";
let searchDebounceTimer = null;
let libraryRequestId = 0;
let libraryAbortController = null;

const SHELF_PREDICATES = {
    all: () => true,
    quero_ler: (d) => d.progress_status === "quero_ler",
    lendo: (d) => d.progress_status === "lendo",
    lido: (d) => d.progress_status === "lido",
    abandonado: (d) => d.progress_status === "abandonado",
};

function populateCollectionFilter() {
    const collections = [...new Set(allFetchedDocs.map((d) => d.collection).filter(Boolean))].sort();
    libraryCollectionFilter.innerHTML =
        '<option value="">Todas as coleções</option>' +
        collections.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
    if (collections.includes(currentCollection)) {
        libraryCollectionFilter.value = currentCollection;
    } else {
        // Search results can remove the selected collection from the option
        // list. Keep UI and state aligned instead of applying a hidden filter.
        currentCollection = "";
        libraryCollectionFilter.value = "";
    }
    editDocCollectionList.innerHTML = collections.map((c) => `<option value="${escapeHtml(c)}"></option>`).join("");
}

function renderLibrary() {
    documentList.innerHTML = "";
    const predicate = SHELF_PREDICATES[currentShelf] || SHELF_PREDICATES.all;
    const filtered = allFetchedDocs.filter(
        (d) => predicate(d) && (!currentCollection || d.collection === currentCollection)
    );
    if (allFetchedDocs.length === 0) {
        libraryEmpty.textContent = searchQuery
            ? "Nenhum documento corresponde à busca."
            : "Nenhum texto ainda. Cole um texto para começar.";
        libraryEmpty.hidden = false;
    } else if (filtered.length === 0) {
        libraryEmpty.textContent = "Nenhum documento encontrado com esse filtro.";
        libraryEmpty.hidden = false;
    } else {
        libraryEmpty.hidden = true;
    }
    filtered.forEach((doc) => documentList.appendChild(buildDocListItem(doc)));
}

function cancelLibraryRequest() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
    libraryRequestId++;
    if (libraryAbortController) {
        libraryAbortController.abort();
        libraryAbortController = null;
    }
    libraryView.removeAttribute("aria-busy");
}

function resetLibraryState() {
    cancelLibraryRequest();
    allFetchedDocs = [];
    currentShelf = "all";
    currentCollection = "";
    searchQuery = "";
    librarySearchInput.value = "";
    libraryCollectionFilter.value = "";
    documentList.replaceChildren();
    libraryEmpty.hidden = true;
    shelfTabButtons.forEach((btn) => {
        const isActive = btn.dataset.shelf === "all";
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-selected", isActive ? "true" : "false");
        btn.tabIndex = isActive ? 0 : -1;
    });
}

async function fetchLibrary() {
    if (libraryAbortController) libraryAbortController.abort();
    const requestId = ++libraryRequestId;
    const controller = new AbortController();
    libraryAbortController = controller;
    const url = searchQuery ? `/documents?q=${encodeURIComponent(searchQuery)}` : "/documents";
    libraryView.setAttribute("aria-busy", "true");
    try {
        const res = await apiFetch(url, { signal: controller.signal });
        if (requestId !== libraryRequestId || !res.ok) return;
        const docs = await res.json();
        if (requestId !== libraryRequestId) return;
        allFetchedDocs = docs;
        populateCollectionFilter();
        renderLibrary();
    } catch (error) {
        if (error?.name === "AbortError" || requestId !== libraryRequestId) return;
        libraryEmpty.textContent = "Não foi possível atualizar a biblioteca.";
        libraryEmpty.hidden = false;
    } finally {
        if (requestId === libraryRequestId) {
            libraryAbortController = null;
            libraryView.removeAttribute("aria-busy");
        }
    }
}

librarySearchInput.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    // Invalidate the current query immediately, not only after the 300ms
    // debounce. Its late response must not repaint results for stale text.
    cancelLibraryRequest();
    searchDebounceTimer = setTimeout(() => {
        searchQuery = librarySearchInput.value.trim();
        fetchLibrary();
    }, 300);
});

libraryCollectionFilter.addEventListener("change", () => {
    currentCollection = libraryCollectionFilter.value;
    renderLibrary();
});

shelfTabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
        currentShelf = btn.dataset.shelf;
        shelfTabButtons.forEach((b) => {
            const isActive = b === btn;
            b.classList.toggle("active", isActive);
            b.setAttribute("aria-selected", isActive ? "true" : "false");
            b.tabIndex = isActive ? 0 : -1;
        });
        renderLibrary();
    });
});

shelfTabButtons.forEach((btn, index) => {
    btn.addEventListener("keydown", (e) => {
        let targetIndex = null;
        if (e.key === "ArrowRight") targetIndex = (index + 1) % shelfTabButtons.length;
        if (e.key === "ArrowLeft") targetIndex = (index - 1 + shelfTabButtons.length) % shelfTabButtons.length;
        if (e.key === "Home") targetIndex = 0;
        if (e.key === "End") targetIndex = shelfTabButtons.length - 1;
        if (targetIndex === null) return;
        e.preventDefault();
        shelfTabButtons[targetIndex].focus();
        shelfTabButtons[targetIndex].click();
    });
});

// ---- Modal de confirmação para documentos abandonados ----
// Clicar num item abandonado (em qualquer prateleira, inclusive "Todos")
// não abre direto no leitor — pergunta a intenção primeiro. Todas as três
// escolhas abrem o leitor em seguida (o modal nunca bloqueia a exploração).
let abandonedModalDoc = null;

function openAbandonedModal(doc) {
    abandonedModalDoc = doc;
    abandonedModalTitle.textContent = doc.title;
    abandonedModal.hidden = false;
}
function closeAbandonedModal() {
    abandonedModal.hidden = true;
    abandonedModalDoc = null;
}
abandonedModal.addEventListener("click", (e) => {
    if (e.target === abandonedModal) closeAbandonedModal();
});

async function resolveAbandonedAndOpen(newStatus) {
    const doc = abandonedModalDoc;
    closeAbandonedModal();
    if (!doc) return;
    if (newStatus) {
        await apiFetch(`/documents/${doc.id}/progress`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus }),
        });
    }
    showReader(doc.id);
}

abandonedResumeBtn.addEventListener("click", () => resolveAbandonedAndOpen("lendo"));
abandonedWishlistBtn.addEventListener("click", () => resolveAbandonedAndOpen("quero_ler"));
abandonedKeepBtn.addEventListener("click", () => resolveAbandonedAndOpen(null));

// ---- Editar documento (título + coleção) — Fase 7, substitui window.prompt ----
let editDocTarget = null;

function openEditDocModal(doc) {
    editDocTarget = doc;
    editDocTitleInput.value = doc.title;
    editDocCollectionInput.value = doc.collection || "";
    editDocError.hidden = true;
    editDocModal.hidden = false;
    editDocTitleInput.focus();
}
function closeEditDocModal() {
    editDocModal.hidden = true;
    editDocTarget = null;
}
editDocCancelBtn.addEventListener("click", closeEditDocModal);
editDocModal.addEventListener("click", (e) => {
    if (e.target === editDocModal) closeEditDocModal();
});

editDocSaveBtn.addEventListener("click", async () => {
    const doc = editDocTarget;
    if (!doc) return;
    const title = editDocTitleInput.value.trim();
    if (!title) {
        editDocError.textContent = "Título não pode ser vazio.";
        editDocError.hidden = false;
        return;
    }
    const res = await apiFetch(`/documents/${doc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, collection: editDocCollectionInput.value.trim() }),
    });
    if (!res.ok) {
        if (res.status === 401) return;
        editDocError.textContent = await apiErrorMessage(res, "Falha ao salvar o documento.");
        editDocError.hidden = false;
        return;
    }
    closeEditDocModal();
    fetchLibrary();
});

async function deleteDocument(doc) {
    if (!window.confirm(`Excluir "${doc.title}"? Essa ação não pode ser desfeita.`)) {
        return;
    }
    const res = await apiFetch(`/documents/${doc.id}`, { method: "DELETE" });
    if (!res.ok) {
        if (res.status !== 401) alert(await apiErrorMessage(res, "Falha ao excluir o documento."));
        return;
    }
    fetchLibrary();
}

// ---- New document modal (Fase 6: três abas — colar/arquivo/URL) ----
let activeDocTab = "paste";
const DOC_TAB_PANELS = { paste: docTabPastePanel, file: docTabFilePanel, url: docTabUrlPanel };
const DOC_TAB_BUTTONS = [docTabPasteBtn, docTabFileBtn, docTabUrlBtn];

function switchDocTab(tab) {
    activeDocTab = tab;
    DOC_TAB_BUTTONS.forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tab));
    Object.entries(DOC_TAB_PANELS).forEach(([key, panel]) => {
        panel.hidden = key !== tab;
    });
}
docTabPasteBtn.addEventListener("click", () => switchDocTab("paste"));
docTabFileBtn.addEventListener("click", () => switchDocTab("file"));
docTabUrlBtn.addEventListener("click", () => switchDocTab("url"));

function showDocError(message) {
    docError.textContent = message;
    docError.hidden = false;
}

function openModal() {
    docTitleInput.value = "";
    docTextInput.value = "";
    docFileTitleInput.value = "";
    docFileInput.value = "";
    docUrlTitleInput.value = "";
    docUrlInput.value = "";
    docPrivateInput.checked = false;
    docError.hidden = true;
    switchDocTab("paste");
    newDocModal.hidden = false;
    docTitleInput.focus();
}
function closeModal() {
    newDocModal.hidden = true;
}

newDocBtn.addEventListener("click", openModal);
cancelDocBtn.addEventListener("click", closeModal);
newDocModal.addEventListener("click", (e) => {
    if (e.target === newDocModal) closeModal();
});
docTitleInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        saveDocBtn.click();
    }
});
document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!newDocModal.hidden) closeModal();
    if (!loginModal.hidden) closeLoginModal();
    if (!newProfileModal.hidden) closeNewProfileModal();
    if (!abandonedModal.hidden) closeAbandonedModal();
    if (!editDocModal.hidden) closeEditDocModal();
});

saveDocBtn.addEventListener("click", async () => {
    docError.hidden = true;
    const visibility = docPrivateInput.checked ? "private" : "house";
    let res;

    if (activeDocTab === "paste") {
        const text = docTextInput.value.trim();
        if (!text) {
            showDocError("Cole algum texto antes de salvar.");
            return;
        }
        const title = docTitleInput.value.trim() || text.slice(0, 40);
        res = await apiFetch("/documents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, raw_text: text, visibility }),
        });
    } else if (activeDocTab === "file") {
        const file = docFileInput.files[0];
        if (!file) {
            showDocError("Escolha um arquivo.");
            return;
        }
        const formData = new FormData();
        formData.append("file", file);
        formData.append("title", docFileTitleInput.value.trim());
        formData.append("visibility", visibility);
        // Sem Content-Type explícito — o navegador define o boundary do
        // multipart sozinho; setar manualmente quebraria o parsing no servidor.
        res = await apiFetch("/documents/upload", { method: "POST", body: formData });
    } else {
        const url = docUrlInput.value.trim();
        if (!url) {
            showDocError("Cole uma URL.");
            return;
        }
        res = await apiFetch("/documents/url", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, title: docUrlTitleInput.value.trim(), visibility }),
        });
    }

    if (!res.ok) {
        if (res.status !== 401) showDocError(await apiErrorMessage(res, "Falha ao salvar o documento."));
        return;
    }
    const doc = await res.json();
    closeModal();
    showReader(doc.id);
});

// ---- TOC (Fase 6) — botão "≡ Capítulos" na topbar do leitor ----
let currentToc = null;

function renderToc(toc) {
    currentToc = toc;
    tocBtn.hidden = !toc || toc.length === 0;
    tocList.innerHTML = "";
    if (!toc) return;
    toc.forEach((entry) => {
        const li = document.createElement("li");
        li.textContent = entry.title;
        li.addEventListener("click", async () => {
            closeTocDropdown();
            await navigateToToken(entry.token_index);
            saveProgress();
        });
        tocList.appendChild(li);
    });
}

function openTocDropdown() {
    if (!currentToc) return;
    tocDropdown.hidden = false;
}
function closeTocDropdown() {
    tocDropdown.hidden = true;
}
tocBtn.addEventListener("click", () => {
    if (tocDropdown.hidden) openTocDropdown();
    else closeTocDropdown();
});
document.addEventListener("click", (e) => {
    if (tocDropdown.hidden) return;
    if (e.target === tocBtn || tocDropdown.contains(e.target)) return;
    closeTocDropdown();
});

// ---- Init ----
bootstrap();
