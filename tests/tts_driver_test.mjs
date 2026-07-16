import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

class MockAudio {
    constructor() {
        this.listeners = new Map();
        this.preload = "";
        this.src = "";
        this.readyState = 0;
        this.currentTime = 0;
        this.duration = 2;
        this.defaultPlaybackRate = 1;
        this.playbackRate = 1;
        this.preservesPitch = true;
        this.paused = true;
    }

    addEventListener(name, callback) {
        if (!this.listeners.has(name)) this.listeners.set(name, new Set());
        this.listeners.get(name).add(callback);
    }

    removeEventListener(name, callback) {
        this.listeners.get(name)?.delete(callback);
    }

    dispatch(name) {
        for (const callback of this.listeners.get(name) || []) callback({ target: this });
    }

    load() {
        // Reproduce the browser behavior behind the reported regression: a
        // source load restores 1x before metadata becomes available.
        this.playbackRate = 1;
        if (this.src) {
            this.readyState = 1;
            queueMicrotask(() => this.dispatch("loadedmetadata"));
        } else {
            this.readyState = 0;
        }
    }

    async play() {
        this.paused = false;
    }

    pause() {
        this.paused = true;
    }

    removeAttribute(name) {
        if (name === "src") this.src = "";
    }
}

globalThis.Audio = MockAudio;
globalThis.requestAnimationFrame = () => 1;
globalThis.cancelAnimationFrame = () => {};

// The project's browser .js modules live outside a package.json `type: module`.
// Import through a data URL so this harness also runs on the installed Node 18.
const driverSource = await readFile(new URL("../static/js/tts.js", import.meta.url), "utf8");
const driverModuleUrl = `data:text/javascript;base64,${Buffer.from(driverSource).toString("base64")}`;
const { TTSDriver, describeVoice } = await import(driverModuleUrl);

assert.deepEqual(
    describeVoice("pf_dora"),
    {
        id: "pf_dora",
        locale: "Português (Brasil)",
        lang: "pt-BR",
        gender: "feminina",
        order: 1,
        previousModel: false,
        name: "Dora",
        label: "Dora — Português (Brasil) · voz feminina",
    },
);
assert.equal(
    describeVoice("am_v0adam").label,
    "Adam (modelo anterior) — Inglês (EUA) · voz masculina",
);
assert.equal(describeVoice("zf_xiaobei").locale, "Chinês (Mandarim)");
assert.equal(describeVoice("voz_futura").locale, "Idioma não identificado");

const tokens = ["um", "dois.", "três", "quatro."].map((text) => ({
    text,
    sentenceEnd: text.endsWith("."),
}));
const engine = {
    pointer: 0,
    getTokens: () => tokens,
    syncToIndex(index) { this.pointer = index; },
};

const driver = new TTSDriver();
let latestMetrics = null;
driver.configure({
    engine,
    apiFetch: async () => { throw new Error("unexpected fetch"); },
    docId: 1,
    voice: "pf_dora",
    onMetricsChange: (metrics) => { latestMetrics = metrics; },
});
driver.setRate(4);

const generation = driver._generation;
const loaded = await driver._setAudioSrc(driver._audio, "/audio/first.mp3", generation);
assert.equal(loaded, true);
assert.equal(driver._audio.defaultPlaybackRate, 4);
assert.equal(driver._audio.playbackRate, 4, "rate must be restored after load() resets it");

driver._currentBlock = {
    start_token: 0,
    end_token: 2,
    alignment_score: 1,
    timestamps: [
        { idx: 0, start: 0, end: 1 },
        { idx: 1, start: 1, end: 2 },
    ],
};
const nextBlock = {
    start_token: 2,
    end_token: 4,
    alignment_score: 1,
    audio_url: "/audio/second.mp3",
    timestamps: [
        { idx: 2, start: 0, end: 1 },
        { idx: 3, start: 1, end: 2 },
    ],
};
driver._bufferQueue = [nextBlock];
driver._standbyBlock = nextBlock;
driver._standbyReady = true;
driver._standbyAudio.src = nextBlock.audio_url;
driver._standbyAudio.readyState = 1;
driver._standbyAudio.duration = 2;
driver._playing = true;

const endedAudio = driver._audio;
await driver._onEnded({ target: endedAudio });

assert.equal(driver._currentBlock.start_token, 2);
assert.equal(driver._audio.playbackRate, 4, "4x must survive an active/standby rollover");
assert.equal(driver._audio.defaultPlaybackRate, 4);
assert.equal(Math.round(latestMetrics.effectiveWpm), 240, "effective WPM must follow real duration and rate");

// A partially captioned Kokoro stream can still produce one timestamp per
// token because the backend collapses unaligned tokens onto the last known
// time. The old driver accepted that array at 35% coverage, advanced to the
// final token at 6s and then left Focus frozen while the 10s audio continued.
const partialTokens = Array.from({ length: 10 }, (_, index) => ({
    text: `token${index}`,
    sentenceEnd: false,
}));
const partialEngine = {
    pointer: 0,
    getTokens: () => partialTokens,
    syncToIndex(index) { this.pointer = index; },
};
const partialDriver = new TTSDriver();
partialDriver.configure({ engine: partialEngine, docId: 3, voice: "pf_dora" });
partialDriver._audio.duration = 10;
const partialBlock = {
    start_token: 0,
    end_token: 10,
    alignment_score: 0.6,
    timestamps: Array.from({ length: 10 }, (_, index) => index < 6
        ? { idx: index, start: index, end: index + 1 }
        : { idx: index, start: 6, end: 6 }),
};
partialDriver._ensureBlockTimings(partialBlock, partialDriver._audio);
assert.equal(partialBlock.timing_fallback, true, "partial timelines must be repaired");
assert.ok(
    partialDriver._tokenForTime(partialBlock, 6.1) < 9,
    "Focus must not reach the final token while several seconds of audio remain",
);
assert.equal(partialDriver._tokenForTime(partialBlock, 9.9), 9);
partialDriver.stop();

driver.setBufferSeconds(999);
assert.equal(driver._bufferTargetSeconds, 120);
driver.setBufferSeconds(1);
assert.equal(driver._bufferTargetSeconds, 30);

driver.stop();

let activeFetches = 0;
let maxActiveFetches = 0;
const fetchedTokens = [];
const longTokens = Array.from({ length: 1000 }, (_, index) => ({
    text: `palavra${index}`,
    sentenceEnd: index % 25 === 24,
}));
const queueEngine = {
    pointer: 0,
    getTokens: () => longTokens,
    syncToIndex(index) { this.pointer = index; },
};
const queueDriver = new TTSDriver();
queueDriver.configure({
    engine: queueEngine,
    docId: 2,
    voice: "pf_dora",
    apiFetch: async (_url, options) => {
        activeFetches += 1;
        maxActiveFetches = Math.max(maxActiveFetches, activeFetches);
        const token = JSON.parse(options.body).token;
        fetchedTokens.push(token);
        await Promise.resolve();
        activeFetches -= 1;
        const start = Math.floor(token / 250) * 250;
        return {
            ok: true,
            async json() {
                return {
                    start_token: start,
                    end_token: Math.min(1000, start + 250),
                    audio_url: `/audio/${start}.mp3`,
                    alignment_score: 1,
                    timestamps: [{ idx: start, start: 0, end: 100 }],
                };
            },
        };
    },
});
queueDriver.setRate(4);
queueDriver.setBufferSeconds(60);
queueDriver._currentBlock = {
    start_token: 0,
    end_token: 250,
    alignment_score: 1,
    timestamps: [{ idx: 0, start: 0, end: 100 }],
};
queueDriver._standbyAudio.duration = 100;
await queueDriver._fillBuffer(queueDriver._generation);
assert.deepEqual(fetchedTokens, [250, 500, 750]);
assert.equal(maxActiveFetches, 1, "look-ahead generation must remain sequential");
assert.equal(queueDriver._bufferQueue.length, 3);
assert.ok(queueDriver._bufferedSeconds() >= 60);
queueDriver.stop();

console.log("TTSDriver regression harness: OK");
