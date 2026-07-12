import { RSVPEngine } from "./rsvp.js";

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

const playPauseBtn = document.getElementById("play-pause-btn");
const rewindBtn = document.getElementById("rewind-btn");
const forwardBtn = document.getElementById("forward-btn");

const wpmSlider = document.getElementById("wpm-slider");
const wpmValue = document.getElementById("wpm-value");
const chunkSlider = document.getElementById("chunk-slider");
const chunkValue = document.getElementById("chunk-value");
const fontSlider = document.getElementById("font-slider");
const fontValue = document.getElementById("font-value");

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

// ---- RSVP engine wiring ----
const engine = new RSVPEngine({
    onChunk: (tokens) => {
        rsvpDisplay.textContent = tokens.map((t) => t.text).join(" ") || "Fim";
    },
    onProgress: (fraction) => {
        progressFill.style.width = `${Math.min(100, fraction * 100)}%`;
    },
    onEnd: () => {
        playPauseBtn.textContent = "▶";
    },
});

function refreshPlayButton() {
    playPauseBtn.textContent = engine.playing ? "⏸" : "▶";
}

playPauseBtn.addEventListener("click", () => {
    engine.toggle();
    refreshPlayButton();
});
rewindBtn.addEventListener("click", () => {
    engine.rewind();
    refreshPlayButton();
});
forwardBtn.addEventListener("click", () => {
    engine.forward();
    refreshPlayButton();
});

wpmSlider.addEventListener("input", () => {
    engine.setWpm(Number(wpmSlider.value));
    wpmValue.textContent = wpmSlider.value;
});
chunkSlider.addEventListener("input", () => {
    engine.setChunkSize(Number(chunkSlider.value));
    chunkValue.textContent = chunkSlider.value;
});
fontSlider.addEventListener("input", () => {
    rsvpDisplay.style.fontSize = `${fontSlider.value}px`;
    fontValue.textContent = fontSlider.value;
});

document.addEventListener("keydown", (e) => {
    if (readerView.hidden) return;
    if (e.code === "Space") {
        e.preventDefault();
        engine.toggle();
        refreshPlayButton();
    } else if (e.code === "ArrowLeft") {
        engine.rewind();
        refreshPlayButton();
    } else if (e.code === "ArrowRight") {
        engine.forward();
        refreshPlayButton();
    } else if (e.code === "ArrowUp") {
        wpmSlider.value = Math.min(1000, Number(wpmSlider.value) + 10);
        wpmSlider.dispatchEvent(new Event("input"));
    } else if (e.code === "ArrowDown") {
        wpmSlider.value = Math.max(100, Number(wpmSlider.value) - 10);
        wpmSlider.dispatchEvent(new Event("input"));
    }
});

// ---- Navigation ----
function showLibrary() {
    engine.pause();
    readerView.hidden = true;
    libraryView.hidden = false;
    loadLibrary();
    history.replaceState(null, "", "#/");
}

async function showReader(id) {
    const res = await fetch(`/documents/${id}`);
    if (!res.ok) {
        alert("Não foi possível carregar o documento.");
        return;
    }
    const doc = await res.json();
    readerTitle.textContent = doc.title;
    engine.setWpm(Number(wpmSlider.value));
    engine.setChunkSize(Number(chunkSlider.value));
    engine.load(doc.raw_text);
    refreshPlayButton();
    libraryView.hidden = true;
    readerView.hidden = false;
    history.replaceState(null, "", `#/read/${id}`);
}

backBtn.addEventListener("click", showLibrary);

// ---- Library ----
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
        li.querySelector(".doc-meta").textContent = `${doc.format.toUpperCase()} · ${new Date(doc.created_at + "Z").toLocaleString()}`;
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
        alert("Falha ao renomear o documento.");
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
        alert("Falha ao excluir o documento.");
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
        alert("Falha ao salvar o documento.");
        return;
    }
    const doc = await res.json();
    closeModal();
    showReader(doc.id);
});

// ---- Init ----
loadLibrary();
