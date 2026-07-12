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

// ---- RSVP engine wiring ----
const engine = new RSVPEngine({
    onChunk: (tokens) => {
        const plain = tokens.map((t) => t.text).join(" ");
        renderChunk(tokens);
        fitDisplayText(plain);
    },
    onProgress: (fraction) => {
        progressFill.style.width = `${Math.min(100, fraction * 100)}%`;
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
    playPauseBtn.textContent = engine.playing ? "⏸" : "▶";
    if (engine.playing) {
        acquireWakeLock();
    } else {
        releaseWakeLock();
    }
}

playPauseBtn.addEventListener("click", () => {
    engine.toggle();
    refreshPlayButton();
    playPauseBtn.blur();
});
rewindBtn.addEventListener("click", () => {
    engine.rewind();
    refreshPlayButton();
    rewindBtn.blur();
});
forwardBtn.addEventListener("click", () => {
    engine.forward();
    refreshPlayButton();
    forwardBtn.blur();
});
rsvpStage.addEventListener("click", () => {
    engine.toggle();
    refreshPlayButton();
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
        engine.toggle();
        refreshPlayButton();
    } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        engine.rewind();
        refreshPlayButton();
    } else if (e.code === "ArrowRight") {
        e.preventDefault();
        engine.forward();
        refreshPlayButton();
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
    engine.setWpm(Number(wpmSlider.value));
    engine.setChunkSize(Number(chunkSlider.value));
    engine.load(doc.raw_text);
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
