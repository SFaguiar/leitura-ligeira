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

const navOpenBtn = document.getElementById("nav-open-btn");
const navPanel = document.getElementById("nav-panel");
const navPanelContent = document.getElementById("nav-panel-content");
const navPanelClose = document.getElementById("nav-panel-close");
const navBackToPositionBtn = document.getElementById("nav-back-to-position");
const navCloseToggle = document.getElementById("nav-close-toggle");
const navPauseToggle = document.getElementById("nav-pause-toggle");
const navRewindBtn = document.getElementById("nav-rewind-btn");
const navPlayPauseBtn = document.getElementById("nav-play-pause-btn");
const navForwardBtn = document.getElementById("nav-forward-btn");

const rsvpStage = document.getElementById("rsvp-stage");
const playPauseBtn = document.getElementById("play-pause-btn");
const rewindBtn = document.getElementById("rewind-btn");
const forwardBtn = document.getElementById("forward-btn");

const wpmSlider = document.getElementById("wpm-slider");
const wpmValue = document.getElementById("wpm-value");
const chunkSlider = document.getElementById("chunk-slider");
const chunkValue = document.getElementById("chunk-value");
const fontSlider = document.getElementById("font-slider");
const fontValue = document.getElementById("font-value");
const orpToggle = document.getElementById("orp-toggle");

const themeToggle = document.getElementById("theme-toggle");

// ---- Theme ----
function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
    localStorage.setItem("theme", theme);
}
applyTheme(localStorage.getItem("theme") || "light");
themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    applyTheme(current === "dark" ? "light" : "dark");
});

// ---- Persisted reader settings (WPM / chunk size / font) ----
const SETTINGS_KEYS = { wpm: "settings.wpm", chunk: "settings.chunkSize", font: "settings.fontSize" };

function loadPersistedSettings() {
    const wpm = localStorage.getItem(SETTINGS_KEYS.wpm);
    const chunk = localStorage.getItem(SETTINGS_KEYS.chunk);
    const font = localStorage.getItem(SETTINGS_KEYS.font);
    if (wpm) {
        wpmSlider.value = wpm;
        wpmValue.textContent = wpm;
    }
    if (chunk) {
        chunkSlider.value = chunk;
        chunkValue.textContent = chunk;
    }
    if (font) {
        fontSlider.value = font;
        fontValue.textContent = font;
        rsvpDisplay.style.fontSize = `${font}px`;
    }
}
loadPersistedSettings();

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

// ---- ORP (Optimal Recognition Point) ----
let orpEnabled = localStorage.getItem("settings.orp") === "1";

function applyOrpToggleUI() {
    orpToggle.textContent = orpEnabled ? "Ligado" : "Desligado";
    orpToggle.classList.toggle("active", orpEnabled);
}
applyOrpToggleUI();

orpToggle.addEventListener("click", () => {
    orpEnabled = !orpEnabled;
    localStorage.setItem("settings.orp", orpEnabled ? "1" : "0");
    applyOrpToggleUI();
    engine.rerender();
});

// ---- Navigation panel settings (both default off) ----
let navCloseOnClick = localStorage.getItem("settings.navCloseOnClick") === "1";
let navPauseOnOpen = localStorage.getItem("settings.navPauseOnOpen") === "1";

function applyNavToggleUI() {
    navCloseToggle.textContent = navCloseOnClick ? "Ligado" : "Desligado";
    navCloseToggle.classList.toggle("active", navCloseOnClick);
    navPauseToggle.textContent = navPauseOnOpen ? "Ligado" : "Desligado";
    navPauseToggle.classList.toggle("active", navPauseOnOpen);
}
applyNavToggleUI();

navCloseToggle.addEventListener("click", () => {
    navCloseOnClick = !navCloseOnClick;
    localStorage.setItem("settings.navCloseOnClick", navCloseOnClick ? "1" : "0");
    applyNavToggleUI();
});
navPauseToggle.addEventListener("click", () => {
    navPauseOnOpen = !navPauseOnOpen;
    localStorage.setItem("settings.navPauseOnOpen", navPauseOnOpen ? "1" : "0");
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

// ---- Navigation panel (full-text, click-to-jump) ----
// Built once per document and cached — reopening the panel doesn't rebuild
// the DOM. One click listener on the container (event delegation) instead of
// one per word, since a document can have tens of thousands of tokens.
let navPanelBuiltForTokens = null;
let navWordEls = [];
let navFollowMode = true;
let navAutoScrolling = false;
let navAutoScrollTimer = null;
let navLastHighlighted = null;

function buildNavPanel(tokens) {
    if (navPanelBuiltForTokens === tokens) return;
    navPanelContent.innerHTML = "";
    const frag = document.createDocumentFragment();
    let paragraphEl = document.createElement("div");
    paragraphEl.className = "nav-paragraph";
    tokens.forEach((token, idx) => {
        const span = document.createElement("span");
        span.className = "nav-word";
        span.textContent = token.text;
        span.dataset.idx = idx;
        paragraphEl.appendChild(span);
        paragraphEl.appendChild(document.createTextNode(" "));
        if (token.paragraphEnd) {
            frag.appendChild(paragraphEl);
            paragraphEl = document.createElement("div");
            paragraphEl.className = "nav-paragraph";
        }
    });
    frag.appendChild(paragraphEl);
    navPanelContent.appendChild(frag);
    navWordEls = navPanelContent.querySelectorAll(".nav-word");
    navPanelBuiltForTokens = tokens;
    navLastHighlighted = null;
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

function scrollToCurrentWord(behavior) {
    const el = navWordEls[engine.pointer];
    if (!el) return;
    navAutoScrolling = true;
    el.scrollIntoView({ block: "center", behavior });
    clearTimeout(navAutoScrollTimer);
    navAutoScrollTimer = setTimeout(() => {
        navAutoScrolling = false;
    }, 200);
}

function updateNavHighlight() {
    if (navPanel.hidden || !navWordEls.length) return;
    const el = navWordEls[engine.pointer];
    if (!el) return;
    if (navLastHighlighted) navLastHighlighted.classList.remove("nav-current");
    el.classList.add("nav-current");
    navLastHighlighted = el;
    if (navFollowMode) scrollToCurrentWord("auto");
}

navPanelContent.addEventListener("scroll", () => {
    if (navAutoScrolling) return;
    if (navFollowMode) {
        navFollowMode = false;
        navBackToPositionBtn.hidden = false;
    }
});

navBackToPositionBtn.addEventListener("click", () => {
    navFollowMode = true;
    navBackToPositionBtn.hidden = true;
    scrollToCurrentWord("smooth");
});

navPanelContent.addEventListener("click", (e) => {
    const wordEl = e.target.closest(".nav-word");
    if (!wordEl) return;
    engine.seekToIndex(Number(wordEl.dataset.idx));
    refreshPlayButton();
    if (navCloseOnClick) closeNavPanel();
});

function openNavPanel() {
    const tokens = engine.getTokens();
    if (!tokens.length) return; // nothing loaded yet — never cache an empty build
    buildNavPanel(tokens);
    if (navPauseOnOpen) {
        engine.pause();
        refreshPlayButton();
    }
    navFollowMode = true;
    navBackToPositionBtn.hidden = true;
    navPanel.hidden = false;
    updateNavHighlight();
    scrollToCurrentWord("auto");
}

function closeNavPanel() {
    navPanel.hidden = true;
}

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

navOpenBtn.addEventListener("click", openNavPanel);
navPanelClose.addEventListener("click", closeNavPanel);

// ---- RSVP engine wiring ----
const engine = new RSVPEngine({
    onChunk: (tokens) => {
        const plain = tokens.map((t) => t.text).join(" ");
        renderChunk(tokens);
        fitDisplayText(plain);
    },
    onProgress: (fraction, pointer, total) => {
        progressFill.style.width = `${Math.min(100, fraction * 100)}%`;
        updateLiveCounter(pointer, total);
        updateNavHighlight();
    },
    onEnd: () => {
        refreshPlayButton();
        rsvpDisplay.classList.remove("orp-single");
        rsvpDisplay.textContent = "Fim";
        fitDisplayText("Fim");
        progressFill.style.width = "100%";
    },
});

function refreshPlayButton() {
    // Two transport bars share one engine: the main reader controls and the
    // panel controls. Keep both play icons in sync.
    const icon = engine.playing ? "⏸" : "▶";
    playPauseBtn.textContent = icon;
    navPlayPauseBtn.textContent = icon;
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
navPlayPauseBtn.addEventListener("click", () => doTogglePlay(navPlayPauseBtn));
navRewindBtn.addEventListener("click", () => doRewind(navRewindBtn));
navForwardBtn.addEventListener("click", () => doForward(navForwardBtn));
rsvpStage.addEventListener("click", () => doTogglePlay());

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
    localStorage.setItem(SETTINGS_KEYS.wpm, wpmSlider.value);
});
chunkSlider.addEventListener("input", () => {
    engine.setChunkSize(Number(chunkSlider.value));
    chunkValue.textContent = chunkSlider.value;
    localStorage.setItem(SETTINGS_KEYS.chunk, chunkSlider.value);
});
fontSlider.addEventListener("input", () => {
    fontValue.textContent = fontSlider.value;
    localStorage.setItem(SETTINGS_KEYS.font, fontSlider.value);
    fitDisplayText();
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
// reader → library instead of leaving the site, and reloading inside the
// reader (or following a #/read/{id} link) opens straight to that document.
function showLibrary(push = true) {
    engine.pause();
    readerView.hidden = true;
    libraryView.hidden = false;
    loadLibrary();
    if (push) history.pushState({ view: "library" }, "", "#/");
}

async function showReader(id, push = true) {
    const res = await fetch(`/documents/${id}`);
    if (!res.ok) {
        alert("Não foi possível carregar o documento.");
        return;
    }
    const doc = await res.json();
    readerTitle.textContent = doc.title;
    // Reveal the reader view *before* loading — engine.load() renders the
    // first chunk synchronously via onChunk, and fitDisplayText() needs
    // rsvp-stage to already have real layout dimensions (a hidden element
    // measures 0-width, which forced every opening word to shrink to the
    // minimum font size).
    libraryView.hidden = true;
    readerView.hidden = false;
    closeNavPanel();
    navPanelBuiltForTokens = null;
    engine.setWpm(Number(wpmSlider.value));
    engine.setChunkSize(Number(chunkSlider.value));
    engine.load(doc.raw_text);
    buildParagraphMarks(engine.getTokens());
    refreshPlayButton();
    if (push) history.pushState({ view: "reader", id }, "", `#/read/${id}`);
}

window.addEventListener("popstate", (e) => {
    const state = e.state;
    if (state && state.view === "reader") {
        showReader(state.id, false);
    } else {
        showLibrary(false);
    }
});

function initFromLocation() {
    const match = location.hash.match(/^#\/read\/(\d+)$/);
    if (match) {
        history.replaceState({ view: "reader", id: Number(match[1]) }, "", location.hash);
        showReader(Number(match[1]), false);
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
    const wpm = Number(wpmSlider.value) || 300;
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
    if (e.key === "Escape") {
        if (!newDocModal.hidden) closeModal();
        else if (!navPanel.hidden) closeNavPanel();
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
