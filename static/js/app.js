import { RSVPEngine, computeOrpIndex } from "./rsvp.js";

const libraryView = document.getElementById("library-view");
const readerView = document.getElementById("reader-view");
const documentList = document.getElementById("document-list");
const libraryEmpty = document.getElementById("library-empty");

const newDocBtn = document.getElementById("new-doc-btn");
const newDocModal = document.getElementById("new-doc-modal");
const docTitleInput = document.getElementById("doc-title");
const docTextInput = document.getElementById("doc-text");
const saveDocBtn = document.getElementById("save-doc-btn");
const cancelDocBtn = document.getElementById("cancel-doc-btn");

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

const wpmSlider = document.getElementById("wpm-slider");
const wpmValue = document.getElementById("wpm-value");
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

// ---- Settings module (single source of truth) ----
// Everything the reader remembers goes through get/set here, under one
// naming convention. Fase 4 (contas) redirects this module to the server —
// having one seam instead of ~6 scattered localStorage call sites is the
// whole point of doing this now.
const SETTINGS_PREFIX = "settings.";
const SETTINGS_TYPES = {
    theme: "string",
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
};
const SETTINGS_DEFAULTS = {
    theme: "light",
    activeMode: "focus",
    wpmFocus: 300,
    chunkFocus: 1,
    fontFocus: 48,
    chunkFlow: 1,
    fontFlow: 20,
    orpEnabled: false,
    navSnapBackOnClick: false,
    navPauseOnSwitch: false,
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
}

function modeKey(base) {
    return `${base}${activeMode === "focus" ? "Focus" : "Flow"}`;
}

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

// ---- Reading mode (Foco / Fluxo) ----
// The motor (rsvp.js) has no concept of mode — it just advances a pointer
// and emits events. Mode only decides which region renders that pointer.
let activeMode = "focus";
let currentDocId = null;

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
    engine.setChunkSize(Number(chunkVal));

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

async function acquireWakeLock() {
    if (!("wakeLock" in navigator)) return;
    try {
        wakeLock = await navigator.wakeLock.request("screen");
        wakeLock.addEventListener("release", () => {
            wakeLock = null;
        });
    } catch (err) {
        wakeLock = null;
    }
}

function releaseWakeLock() {
    if (wakeLock) {
        wakeLock.release().catch(() => {});
        wakeLock = null;
    }
}

document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && engine.playing && !wakeLock) {
        acquireWakeLock();
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
let flowBuiltForTokens = null;
let flowWordEls = [];
let flowFollowMode = true;
let flowAutoScrolling = false;
let flowAutoScrollTimer = null;
let flowHighlightedEls = [];
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function buildFlowContent(tokens) {
    if (flowBuiltForTokens === tokens) return;
    flowContent.innerHTML = "";
    const frag = document.createDocumentFragment();
    let paragraphEl = document.createElement("div");
    paragraphEl.className = "flow-paragraph";
    tokens.forEach((token, idx) => {
        const span = document.createElement("span");
        span.className = "flow-word";
        span.textContent = token.text;
        span.dataset.idx = idx;
        paragraphEl.appendChild(span);
        paragraphEl.appendChild(document.createTextNode(" "));
        if (token.paragraphEnd) {
            frag.appendChild(paragraphEl);
            paragraphEl = document.createElement("div");
            paragraphEl.className = "flow-paragraph";
        }
    });
    frag.appendChild(paragraphEl);
    flowContent.appendChild(frag);
    flowWordEls = flowContent.querySelectorAll(".flow-word");
    flowBuiltForTokens = tokens;
    flowHighlightedEls = [];
}

function ensureFlowBuilt() {
    const tokens = engine.getTokens();
    if (!tokens.length) return;
    buildFlowContent(tokens);
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
    }, 200);
}

// Highlights the *whole* chunk currently on screen (all N words when
// "palavras por vez" > 1), not just its first word — so Flow matches what
// Focus is actually flashing instead of looking like it skipped words.
function updateFlowHighlight(chunkTokens) {
    if (flowRegion.hidden || !flowWordEls.length) return;
    const start = engine.pointer;
    const count = chunkTokens ? chunkTokens.length : 1;
    flowHighlightedEls.forEach((el) => el.classList.remove("flow-current"));
    flowHighlightedEls = [];
    for (let i = start; i < start + count && i < flowWordEls.length; i++) {
        const el = flowWordEls[i];
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
    engine.seekToIndex(Number(wordEl.dataset.idx));
    refreshPlayButton();
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
    },
});

function refreshPlayButton() {
    playPauseBtn.textContent = engine.playing ? "⏸" : "▶";
    if (engine.playing) {
        acquireWakeLock();
    } else {
        releaseWakeLock();
    }
}

function doTogglePlay(btn) {
    engine.toggle();
    refreshPlayButton();
    if (btn) btn.blur();
}
function doRewind(btn) {
    engine.rewind();
    refreshPlayButton();
    if (btn) btn.blur();
}
function doForward(btn) {
    engine.forward();
    refreshPlayButton();
    if (btn) btn.blur();
}

playPauseBtn.addEventListener("click", () => doTogglePlay(playPauseBtn));
rewindBtn.addEventListener("click", () => doRewind(rewindBtn));
forwardBtn.addEventListener("click", () => doForward(forwardBtn));
rsvpStage.addEventListener("click", () => doTogglePlay());

// ---- Mode switching ----
// Entering Flow pushes a history entry; the Foco button (and the Android
// back gesture) pop it via history.back() instead of pushing another entry
// — mirrors the library/reader back-button pattern already in this app.
function switchMode(mode, { push = true } = {}) {
    if (mode === activeMode) return;
    if (navPauseOnSwitch && engine.playing) {
        engine.pause();
    }
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
    engine.seekFraction(fraction);
    refreshPlayButton();
}

let scrubbing = false;
scrubber.addEventListener("pointerdown", (e) => {
    scrubbing = true;
    scrubber.setPointerCapture(e.pointerId);
    seekFromPointerEvent(e);
});
scrubber.addEventListener("pointermove", (e) => {
    if (scrubbing) seekFromPointerEvent(e);
});
scrubber.addEventListener("pointerup", () => {
    scrubbing = false;
});
scrubber.addEventListener("pointercancel", () => {
    scrubbing = false;
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
        wpmSlider.value = Math.min(1000, Number(wpmSlider.value) + 10);
        wpmSlider.dispatchEvent(new Event("input"));
    } else if (e.code === "ArrowDown") {
        e.preventDefault();
        wpmSlider.value = Math.max(100, Number(wpmSlider.value) - 10);
        wpmSlider.dispatchEvent(new Event("input"));
    }
});

// ---- Navigation ----
// Real history entries (pushState) so the Android back gesture/button moves
// reader → library instead of leaving the site, reloading inside the reader
// (or following a #/read/{id}/{mode} link) opens straight to that document
// and mode, and Fluxo→Foco→biblioteca pops one level at a time.
function showLibrary(push = true) {
    engine.pause();
    readerView.hidden = true;
    libraryView.hidden = false;
    currentDocId = null;
    loadLibrary();
    if (push) history.pushState({ view: "library" }, "", "#/");
}

async function showReader(id, push = true, mode = "focus") {
    const res = await fetch(`/documents/${id}`);
    if (!res.ok) {
        alert("Não foi possível carregar o documento.");
        return;
    }
    const doc = await res.json();
    currentDocId = id;
    readerTitle.textContent = doc.title;
    // Reveal the reader view — and the correct mode region — *before*
    // loading. engine.load() renders the first chunk synchronously via
    // onChunk, and fitDisplayText() needs rsvp-stage to already have real
    // layout dimensions (a hidden element measures 0-width, which forced
    // every opening word to shrink to the minimum font size).
    libraryView.hidden = true;
    readerView.hidden = false;
    activeMode = mode;
    setSetting("activeMode", mode);
    applyModeUI(mode);
    applyFontSliderRange();
    loadModeSliders();
    updateOrpVisibility();
    updateSnapBackVisibility();

    flowBuiltForTokens = null; // new document — Flow's cached spans are stale
    engine.load(doc.raw_text);
    buildParagraphMarks(engine.getTokens());
    if (mode === "flow") {
        // load() already fired one render before Flow's spans existed for
        // these tokens (buildFlowContent needs the tokens engine.load() just
        // produced) — build now, then render again so the highlight lands.
        ensureFlowBuilt();
        engine.rerender();
    }
    refreshPlayButton();
    if (push) history.pushState({ view: "reader", id, mode }, "", `#/read/${id}/${mode}`);
}

window.addEventListener("popstate", (e) => {
    const state = e.state;
    if (state && state.view === "reader") {
        if (state.id === currentDocId) {
            switchMode(state.mode, { push: false });
        } else {
            showReader(state.id, false, state.mode || "focus");
        }
    } else {
        showLibrary(false);
    }
});

function initFromLocation() {
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
async function apiErrorMessage(res, fallback) {
    try {
        const body = await res.json();
        return body.detail || fallback;
    } catch {
        return fallback;
    }
}

function estimatedMinutes(wordCount) {
    const wpm = getSetting("wpmFocus") || 300;
    return Math.max(1, Math.round(wordCount / wpm));
}

async function loadLibrary() {
    const res = await fetch("/documents");
    const docs = await res.json();
    documentList.innerHTML = "";
    libraryEmpty.hidden = docs.length > 0;
    docs.forEach((doc) => {
        const li = document.createElement("li");
        li.innerHTML = `
            <div class="doc-info">
                <div class="doc-title"></div>
                <div class="doc-meta"></div>
            </div>
            <div class="doc-actions">
                <button class="icon-btn rename-btn" title="Renomear">✏️</button>
                <button class="icon-btn delete-btn" title="Excluir">🗑️</button>
            </div>
        `;
        li.querySelector(".doc-title").textContent = doc.title;
        li.querySelector(".doc-meta").textContent =
            `${doc.format.toUpperCase()} · ${doc.word_count.toLocaleString()} palavras · ` +
            `~${estimatedMinutes(doc.word_count)} min · ${new Date(doc.created_at).toLocaleString()}`;
        li.querySelector(".doc-info").addEventListener("click", () => showReader(doc.id));
        li.querySelector(".rename-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            renameDocument(doc);
        });
        li.querySelector(".delete-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            deleteDocument(doc);
        });
        documentList.appendChild(li);
    });
}

async function renameDocument(doc) {
    const newTitle = window.prompt("Novo título:", doc.title);
    if (newTitle === null) return;
    const trimmed = newTitle.trim();
    if (!trimmed || trimmed === doc.title) return;

    const res = await fetch(`/documents/${doc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmed }),
    });
    if (!res.ok) {
        alert(await apiErrorMessage(res, "Falha ao renomear o documento."));
        return;
    }
    loadLibrary();
}

async function deleteDocument(doc) {
    if (!window.confirm(`Excluir "${doc.title}"? Essa ação não pode ser desfeita.`)) {
        return;
    }
    const res = await fetch(`/documents/${doc.id}`, { method: "DELETE" });
    if (!res.ok) {
        alert(await apiErrorMessage(res, "Falha ao excluir o documento."));
        return;
    }
    loadLibrary();
}

// ---- New document modal ----
function openModal() {
    docTitleInput.value = "";
    docTextInput.value = "";
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
    if (e.key === "Escape" && !newDocModal.hidden) {
        closeModal();
    }
});

saveDocBtn.addEventListener("click", async () => {
    const text = docTextInput.value.trim();
    if (!text) {
        alert("Cole algum texto antes de salvar.");
        return;
    }
    const title = docTitleInput.value.trim() || text.slice(0, 40);
    const res = await fetch("/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, raw_text: text }),
    });
    if (!res.ok) {
        alert(await apiErrorMessage(res, "Falha ao salvar o documento."));
        return;
    }
    const doc = await res.json();
    closeModal();
    showReader(doc.id);
});

// ---- Init ----
initFromLocation();
