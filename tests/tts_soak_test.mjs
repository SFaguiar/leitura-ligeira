import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

class SoakAudio {
    constructor() {
        this.listeners = new Map();
        this.preload = "";
        this.src = "";
        this.readyState = 0;
        this.currentTime = 0;
        this.duration = 5;
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

globalThis.Audio = SoakAudio;
globalThis.requestAnimationFrame = () => 1;
globalThis.cancelAnimationFrame = () => {};

const driverSource = await readFile(new URL("../static/js/tts.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(driverSource).toString("base64")}`;
const { TTSDriver } = await import(moduleUrl);

const BLOCK_WORDS = 50;
const BLOCK_COUNT = 120;
const TOTAL_TOKENS = BLOCK_WORDS * BLOCK_COUNT;
const tokens = Array.from({ length: TOTAL_TOKENS }, (_, index) => ({
    text: `palavra${index}`,
    sentenceEnd: index % 10 === 9,
}));
let lastPointer = 0;
const engine = {
    pointer: 0,
    getTokens: () => tokens,
    syncToIndex(index) {
        assert.ok(index >= lastPointer, `pointer regressed from ${lastPointer} to ${index}`);
        this.pointer = index;
        lastPointer = index;
    },
};

let activeFetches = 0;
let maxActiveFetches = 0;
let fetchCount = 0;
let endCount = 0;
const errors = [];
const driver = new TTSDriver();
driver.configure({
    engine,
    docId: 77,
    voice: "pf_dora",
    onError: (message) => errors.push(message),
    onEnd: () => { endCount += 1; },
    apiFetch: async (_url, options) => {
        activeFetches += 1;
        maxActiveFetches = Math.max(maxActiveFetches, activeFetches);
        fetchCount += 1;
        await Promise.resolve();
        const token = JSON.parse(options.body).token;
        const start = Math.floor(token / BLOCK_WORDS) * BLOCK_WORDS;
        const end = Math.min(TOTAL_TOKENS, start + BLOCK_WORDS);
        activeFetches -= 1;
        return {
            ok: true,
            async json() {
                return {
                    start_token: start,
                    end_token: end,
                    audio_url: `/audio/${start}.mp3`,
                    alignment_score: 1,
                    timestamps: Array.from({ length: end - start }, (_, offset) => ({
                        idx: start + offset,
                        start: offset * 0.1,
                        end: (offset + 1) * 0.1,
                    })),
                };
            },
        };
    },
});
driver.setRate(4);
driver.setBufferSeconds(120);
await driver.play();
if (driver._bufferFillPromise) await driver._bufferFillPromise;

assert.equal(driver.isPlaying(), true);
assert.equal(driver._currentBlock.start_token, 0);
let rollovers = 0;
while (driver._currentBlock.end_token < TOTAL_TOKENS) {
    driver._audio.currentTime = driver._audio.duration - 0.001;
    driver._tick();
    const expectedLast = driver._currentBlock.end_token - 1;
    assert.equal(engine.pointer, expectedLast, "visual pointer must reach every audio block end");
    const endedAudio = driver._audio;
    await driver._onEnded({ target: endedAudio });
    if (driver._bufferFillPromise) await driver._bufferFillPromise;
    rollovers += 1;
    assert.equal(driver._audio.playbackRate, 4, `4x lost after rollover ${rollovers}`);
    assert.equal(driver._audio.defaultPlaybackRate, 4);
    assert.ok(driver._bufferQueue.length <= 8, "buffer queue exceeded its hard block cap");
}

driver._audio.currentTime = driver._audio.duration - 0.001;
driver._tick();
await driver._onEnded({ target: driver._audio });
assert.equal(engine.pointer, TOTAL_TOKENS - 1);
assert.equal(endCount, 1);
assert.equal(driver.isPlaying(), false);
assert.equal(errors.length, 0, errors.join("; "));
assert.equal(rollovers, BLOCK_COUNT - 1);
assert.equal(fetchCount, BLOCK_COUNT);
assert.equal(maxActiveFetches, 1, "GPU block generation must remain sequential");

driver.reset();
assert.equal(driver._engine, null);
assert.equal(driver._docId, null);
assert.equal(driver._fetchControllers.size, 0);
assert.equal(driver._audio.src, "");
assert.equal(driver._standbyAudio.src, "");

console.log(
    `TTS 4x soak: OK (${BLOCK_COUNT} blocks, ${TOTAL_TOKENS} tokens, ${rollovers} rollovers)`,
);