// TTS driver (Fase 8) — media/clock logic kept OUT of rsvp.js on purpose.
//
// The RSVP engine's own setTimeout loop is silent during TTS; the <audio>
// element is the clock. A rAF loop (plus a `timeupdate` backstop, so it still
// works even where rAF is throttled) reads audio.currentTime, binary-searches
// the block's per-word timestamps, and only calls engine.syncToIndex when the
// token actually changes — never rerendering 60×/s for nothing.
//
// MVP scope (per the deliberated plan): ONE <audio> element, no gapless
// ping-pong. The next block is prefetched (generated server-side + preloaded)
// as soon as the current block STARTS playing, so the GPU+network latency is
// hidden behind the current block instead of leaving a gap at the seam.
//
// Phase 8 hardening keeps that historical constraint documented, but replaces
// it with an active/standby pair plus a bounded sequential look-ahead queue.
// Only the immediate next file is decoded in the standby element; farther
// blocks are generated server-side, which avoids an army of live <audio>s.

const TTS_MIN_ALIGN = 0.85;
const TTS_MAX_DURATION_DRIFT = 0.08;
const TTS_ZERO_SPAN_EPSILON = 0.005;
const TTS_MAX_ZERO_RUN = 3;

const TTS_VOICE_FAMILIES = Object.freeze({
    af: { locale: "Inglês (EUA)", lang: "en-US", gender: "feminina", order: 10 },
    am: { locale: "Inglês (EUA)", lang: "en-US", gender: "masculina", order: 10 },
    bf: { locale: "Inglês (Reino Unido)", lang: "en-GB", gender: "feminina", order: 20 },
    bm: { locale: "Inglês (Reino Unido)", lang: "en-GB", gender: "masculina", order: 20 },
    ef: { locale: "Espanhol", lang: "es", gender: "feminina", order: 30 },
    em: { locale: "Espanhol", lang: "es", gender: "masculina", order: 30 },
    ff: { locale: "Francês", lang: "fr", gender: "feminina", order: 40 },
    fm: { locale: "Francês", lang: "fr", gender: "masculina", order: 40 },
    hf: { locale: "Hindi", lang: "hi", gender: "feminina", order: 50 },
    hm: { locale: "Hindi", lang: "hi", gender: "masculina", order: 50 },
    if: { locale: "Italiano", lang: "it", gender: "feminina", order: 60 },
    im: { locale: "Italiano", lang: "it", gender: "masculina", order: 60 },
    jf: { locale: "Japonês", lang: "ja", gender: "feminina", order: 70 },
    jm: { locale: "Japonês", lang: "ja", gender: "masculina", order: 70 },
    pf: { locale: "Português (Brasil)", lang: "pt-BR", gender: "feminina", order: 1 },
    pm: { locale: "Português (Brasil)", lang: "pt-BR", gender: "masculina", order: 1 },
    zf: { locale: "Chinês (Mandarim)", lang: "zh-CN", gender: "feminina", order: 80 },
    zm: { locale: "Chinês (Mandarim)", lang: "zh-CN", gender: "masculina", order: 80 },
});

export function describeVoice(voice) {
    const id = String(voice || "").trim().toLowerCase();
    const prefix = id.includes("_") ? id.slice(0, id.indexOf("_")) : "";
    const family = TTS_VOICE_FAMILIES[prefix] || {
        locale: "Idioma não identificado",
        lang: "",
        gender: "não identificada",
        order: 999,
    };
    const rawName = id.includes("_") ? id.slice(id.indexOf("_") + 1) : id;
    const previousModel = rawName.startsWith("v0");
    const cleanName = previousModel ? rawName.slice(2) : rawName;
    const name = cleanName
        ? cleanName.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
        : "Voz clássica";
    const version = previousModel && cleanName ? " (modelo anterior)" : "";
    return {
        id,
        locale: family.locale,
        lang: family.lang,
        gender: family.gender,
        order: family.order,
        previousModel,
        name: `${name}${version}`,
        label: `${name}${version} — ${family.locale} · voz ${family.gender}`,
    };
}

export class TTSDriver {
    constructor() {
        this._audio = new Audio();
        this._audio.preload = "auto";
        this._standbyAudio = new Audio();
        this._standbyAudio.preload = "auto";
        this._engine = null;
        this._apiFetch = null;
        this._docId = null;
        this._voice = null;
        this._currentBlock = null;
        this._prefetched = null;
        this._prefetchEl = null;
        this._bufferQueue = [];
        this._bufferTargetSeconds = 60;
        this._maxBufferedBlocks = 8;
        this._bufferFillPromise = null;
        this._standbyBlock = null;
        this._standbyReady = false;
        this._rate = 1;
        this._metricSamples = [];
        this._playing = false;
        this._loading = false;
        this._raf = null;
        this._lastIdx = -1;
        this._generation = 0;
        this._fetchControllers = new Set();
        this._audioLoadCancels = new Set();
        this._onError = () => {};
        this._onEnd = () => {};
        this._onStateChange = () => {};
        this._onBlockChange = () => {};
        this._onMetricsChange = () => {};
        this._onBufferChange = () => {};

        this._tick = this._tick.bind(this);
        this._onEnded = this._onEnded.bind(this);
        this._audio.addEventListener("ended", this._onEnded);
        this._standbyAudio.addEventListener("ended", this._onEnded);
    }

    configure({
        engine,
        apiFetch,
        docId,
        voice,
        onError,
        onEnd,
        onStateChange,
        onBlockChange,
        onMetricsChange,
        onBufferChange,
    }) {
        const contextChanged = this._engine !== engine || this._docId !== docId;
        if (contextChanged) this.stop();
        this._engine = engine;
        this._apiFetch = apiFetch;
        this._docId = docId;
        this._voice = voice;
        if (onError) this._onError = onError;
        if (onEnd) this._onEnd = onEnd;
        if (onStateChange) this._onStateChange = onStateChange;
        if (onBlockChange) this._onBlockChange = onBlockChange;
        if (onMetricsChange) this._onMetricsChange = onMetricsChange;
        if (onBufferChange) this._onBufferChange = onBufferChange;
    }

    isPlaying() {
        return this._playing;
    }

    isLoading() {
        return this._loading;
    }

    _notifyState() {
        this._onStateChange({ playing: this._playing, loading: this._loading });
    }

    _setLoading(loading) {
        if (this._loading === loading) return;
        this._loading = loading;
        this._notifyState();
    }

    // Every play/seek/voice/document transition owns a generation. Advancing
    // it makes every older fetch, metadata listener and block hand-off stale,
    // so a late network response can never resurrect audio after stop/logout.
    _invalidateAsync() {
        this._generation += 1;
        this._fetchControllers.forEach((controller) => controller.abort());
        this._fetchControllers.clear();
        this._audioLoadCancels.forEach((cancel) => cancel());
        this._audioLoadCancels.clear();
        return this._generation;
    }

    _isCurrent(generation) {
        return generation === this._generation;
    }

    _clearPrefetchAudio() {
        if (!this._prefetchEl) return;
        this._prefetchEl.pause();
        this._prefetchEl.removeAttribute("src");
        this._prefetchEl.load();
        this._prefetchEl = null;
    }

    _releaseAudio(audio) {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
        this._applyRate(audio);
    }

    _applyRate(audio) {
        if (!audio) return;
        // defaultPlaybackRate is the value browsers restore after a source
        // swap/ended transition; playbackRate is the effective current value.
        audio.defaultPlaybackRate = this._rate;
        audio.playbackRate = this._rate;
        audio.preservesPitch = true;
    }

    setRate(rate) {
        // Reading audio.currentTime in the clock loop means changing the audio
        // rate speeds up the RSVP advance for free — no engine recalculation.
        const safeRate = Math.max(0.5, Math.min(4, Number(rate) || 1));
        this._rate = safeRate;
        this._applyRate(this._audio);
        this._applyRate(this._standbyAudio);
        this._notifyMetrics();
        this._notifyBuffer();
        if (this._currentBlock) this._fillBuffer(this._generation);
    }

    setBufferSeconds(seconds) {
        this._bufferTargetSeconds = Math.max(30, Math.min(120, Number(seconds) || 60));
        this._notifyBuffer();
        if (this._currentBlock) this._fillBuffer(this._generation);
    }

    _blockBaseDuration(block) {
        const timestamps = Array.isArray(block?.timestamps) ? block.timestamps : [];
        const timestampEnd = timestamps.reduce(
            (max, entry) => Math.max(max, Number(entry.end) || 0),
            0,
        );
        if (timestampEnd > 0) return timestampEnd;
        const words = Math.max(1, Number(block?.end_token) - Number(block?.start_token));
        return words / 180 * 60;
    }

    _bufferedSeconds() {
        return this._bufferQueue.reduce(
            (sum, block) => sum + this._blockBaseDuration(block) / this._rate,
            0,
        );
    }

    _notifyBuffer() {
        this._onBufferChange({
            readySeconds: this._bufferedSeconds(),
            targetSeconds: this._bufferTargetSeconds,
            blocks: this._bufferQueue.length,
        });
    }

    _notifyMetrics() {
        const totalWords = this._metricSamples.reduce((sum, sample) => sum + sample.words, 0);
        const totalDuration = this._metricSamples.reduce((sum, sample) => sum + sample.duration, 0);
        const effectiveWpm = totalDuration > 0
            ? totalWords / totalDuration * 60 * this._rate
            : null;
        this._onMetricsChange({ rate: this._rate, effectiveWpm });
    }

    _clearBuffer() {
        this._bufferQueue = [];
        this._standbyBlock = null;
        this._standbyReady = false;
        this._releaseAudio(this._standbyAudio);
        this._prefetched = null;
        this._clearPrefetchAudio();
        this._notifyBuffer();
    }

    // Voice change invalidates cached blocks (audio is voice-specific).
    setVoice(voice) {
        if (voice === this._voice) return;
        const wasActive = this._playing || this._loading;
        this._invalidateAsync();
        this._playing = false;
        this._loading = false;
        this._audio.pause();
        this._standbyAudio.pause();
        this._stopClock();
        this._releaseAudio(this._audio);
        this._voice = voice;
        this._currentBlock = null;
        this._clearBuffer();
        this._metricSamples = [];
        this._notifyMetrics();
        this._lastIdx = -1;
        if (wasActive) this._notifyState();
    }

    _totalTokens() {
        return this._engine ? this._engine.getTokens().length : 0;
    }

    async _fetchBlock(tokenIdx, generation, { reportErrors = true } = {}) {
        if (!this._apiFetch || !this._docId || !this._isCurrent(generation)) return null;
        const controller = new AbortController();
        this._fetchControllers.add(controller);
        try {
            const res = await this._apiFetch(`/documents/${this._docId}/tts/blocks`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: tokenIdx, voice: this._voice }),
                signal: controller.signal,
            });
            if (!this._isCurrent(generation)) return null;
            if (!res.ok) {
                if (reportErrors && res.status !== 401) {
                    let detail = `Erro ${res.status}`;
                    try {
                        detail = (await res.json()).detail || detail;
                    } catch (_) {}
                    if (this._isCurrent(generation)) this._onError(detail);
                }
                return null;
            }
            const block = await res.json();
            return this._isCurrent(generation) ? block : null;
        } catch (e) {
            if (e.name !== "AbortError" && reportErrors && this._isCurrent(generation)) {
                this._onError("Sem conexão com o servidor de narração.");
            }
            return null;
        } finally {
            this._fetchControllers.delete(controller);
        }
    }

    _setAudioSrc(audio, url, generation) {
        return new Promise((resolve) => {
            let settled = false;
            const finish = (ready) => {
                if (settled) return;
                settled = true;
                audio.removeEventListener("loadedmetadata", onReady);
                audio.removeEventListener("error", onError);
                this._audioLoadCancels.delete(onCancel);
                if (ready) this._applyRate(audio);
                resolve(ready && this._isCurrent(generation));
            };
            const onReady = () => finish(true);
            const onError = () => finish(false);
            const onCancel = () => finish(false);
            this._audioLoadCancels.add(onCancel);
            audio.addEventListener("loadedmetadata", onReady);
            audio.addEventListener("error", onError);
            audio.src = url;
            audio.load();
            if (audio.readyState >= 1) finish(true);
        });
    }

    _ensureBlockTimings(block, audio = this._audio) {
        // Array length alone does not prove that the timeline is complete:
        // the backend emits zero-duration placeholders for tokens absent from
        // Kokoro captions, including fragments returned with timestamps:null.
        // Validate coverage against the real MP3 duration before trusting it.
        // Otherwise Focus can finish visually while audio is still running.
        const count = Math.max(1, block.end_token - block.start_token);
        const timestamps = Array.isArray(block.timestamps) ? block.timestamps : [];
        const duration = Number.isFinite(audio.duration) && audio.duration > 0
            ? audio.duration
            : 0;
        let finalEnd = 0;
        let previousStart = 0;
        let zeroRun = 0;
        let longestZeroRun = 0;
        let structurallyValid = timestamps.length === count;
        if (structurallyValid) {
            timestamps.forEach((entry, offset) => {
                const idx = Number(entry?.idx);
                const start = Number(entry?.start);
                const end = Number(entry?.end);
                if (
                    !Number.isFinite(start)
                    || !Number.isFinite(end)
                    || idx !== block.start_token + offset
                    || start < previousStart
                    || end < start
                ) {
                    structurallyValid = false;
                    return;
                }
                previousStart = start;
                finalEnd = Math.max(finalEnd, end);
                if (end - start <= TTS_ZERO_SPAN_EPSILON) {
                    zeroRun += 1;
                    longestZeroRun = Math.max(longestZeroRun, zeroRun);
                } else {
                    zeroRun = 0;
                }
            });
        }
        const durationRatio = duration > 0 ? finalEnd / duration : 1;
        const coversAudio = durationRatio >= 1 - TTS_MAX_DURATION_DRIFT
            && durationRatio <= 1 + TTS_MAX_DURATION_DRIFT;
        const complete = structurallyValid
            && finalEnd > 0
            && Number(block.alignment_score) >= TTS_MIN_ALIGN
            && longestZeroRun <= TTS_MAX_ZERO_RUN
            && coversAudio;
        if (complete || !duration) return;

        // Low/absent upstream alignment must not freeze the visual pointer at
        // the block start. Distribute the real duration using token length and
        // sentence pauses; it is approximate, monotonic, and bounded.
        const tokens = this._engine?.getTokens().slice(block.start_token, block.end_token) || [];
        const weights = Array.from({ length: count }, (_, offset) => {
            const token = tokens[offset];
            const text = token?.text || "";
            return Math.max(1, text.replace(/\s/g, "").length) + (token?.sentenceEnd ? 3 : 0);
        });
        const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
        let cursor = 0;
        block.timestamps = weights.map((weight, offset) => {
            const start = cursor / totalWeight * duration;
            cursor += weight;
            const end = cursor / totalWeight * duration;
            return { idx: block.start_token + offset, start, end };
        });
        block.timing_fallback = true;
    }

    _recordBlockMetrics(block, audio = this._audio) {
        const duration = Number.isFinite(audio.duration) && audio.duration > 0
            ? audio.duration
            : this._blockBaseDuration(block);
        const words = Math.max(1, block.end_token - block.start_token);
        this._metricSamples = this._metricSamples.filter((sample) => sample.start !== block.start_token);
        this._metricSamples.push({ start: block.start_token, words, duration });
        this._metricSamples = this._metricSamples.slice(-3);
        this._notifyMetrics();
    }

    // Returns the block covering tokenIdx with audio.src loaded, reusing the
    // current or prefetched block when possible, else generating it.
    // The historical single prefetched slot is now a bounded queue; an
    // external seek consumes a matching entry and invalidates the old horizon.
    async _loadBlockForToken(tokenIdx, generation) {
        if (!this._isCurrent(generation)) return null;
        const cur = this._currentBlock;
        if (cur && tokenIdx >= cur.start_token && tokenIdx < cur.end_token) {
            return cur;
        }
        let block = null;
        const queuedIndex = this._bufferQueue.findIndex(
            (candidate) => tokenIdx >= candidate.start_token && tokenIdx < candidate.end_token,
        );
        if (queuedIndex >= 0) {
            block = this._bufferQueue[queuedIndex];
            this._clearBuffer();
        } else {
            this._clearBuffer();
            block = await this._fetchBlock(tokenIdx, generation);
        }
        if (!block || !this._isCurrent(generation)) return null;
        this._currentBlock = block;
        const ready = await this._setAudioSrc(this._audio, block.audio_url, generation);
        if (!ready || !this._isCurrent(generation)) {
            if (this._isCurrent(generation)) this._onError("Não foi possível carregar o áudio narrado.");
            return null;
        }
        this._ensureBlockTimings(block, this._audio);
        this._recordBlockMetrics(block, this._audio);
        this._onBlockChange(block);
        return block;
    }

    _timestampsOffset(block, tokenIdx) {
        // Timestamps are one-per-token, contiguous from start_token, so the
        // entry for a token is a direct offset (O(1)); fall back to a scan.
        const ts = block.timestamps;
        const off = tokenIdx - block.start_token;
        if (off >= 0 && off < ts.length && ts[off].idx === tokenIdx) return ts[off];
        return ts.find((e) => e.idx === tokenIdx) || ts[0] || null;
    }

    _seekAudioToToken(block, tokenIdx) {
        const entry = this._timestampsOffset(block, tokenIdx);
        this._audio.currentTime = entry ? entry.start : 0;
        this._lastIdx = tokenIdx;
    }

    // Binary search: last timestamp whose start <= t → its global token idx.
    _tokenForTime(block, t) {
        const ts = block.timestamps;
        if (!ts.length) return block.start_token;
        let lo = 0;
        let hi = ts.length - 1;
        let res = 0;
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            if (ts[mid].start <= t) {
                res = mid;
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }
        return ts[res].idx;
    }

    _tick() {
        const block = this._currentBlock;
        if (!block || !this._engine) return;
        // Low-alignment block: audio still plays, but the word timings are too
        // rough to karaoke — leave the highlight at the block start instead of
        // twitching it around (per the plan's low-score fallback). The hardened
        // driver replaces that old freeze with monotonic duration-derived
        // timestamps, so the pointer keeps progressing in audio-only mode.
        if (block.alignment_score < TTS_MIN_ALIGN && !block.timing_fallback) {
            this._ensureBlockTimings(block, this._audio);
        }
        const idx = this._tokenForTime(block, this._audio.currentTime);
        if (idx !== this._lastIdx) {
            this._lastIdx = idx;
            this._engine.syncToIndex(idx);
        }
    }

    _startClock() {
        this._stopClock();
        this._audio.addEventListener("timeupdate", this._tick);
        const loop = () => {
            if (!this._playing) return;
            this._tick();
            this._raf = requestAnimationFrame(loop);
        };
        this._raf = requestAnimationFrame(loop);
    }

    _stopClock() {
        if (this._raf !== null) {
            cancelAnimationFrame(this._raf);
            this._raf = null;
        }
        this._audio.removeEventListener("timeupdate", this._tick);
        this._standbyAudio.removeEventListener("timeupdate", this._tick);
    }

    async _primeStandby(generation) {
        const block = this._bufferQueue[0];
        if (!block || !this._isCurrent(generation)) return false;
        if (this._standbyReady && this._standbyBlock?.start_token === block.start_token) {
            return true;
        }
        this._standbyReady = false;
        this._standbyBlock = block;
        this._releaseAudio(this._standbyAudio);
        const ready = await this._setAudioSrc(
            this._standbyAudio,
            block.audio_url,
            generation,
        );
        if (
            !ready
            || !this._isCurrent(generation)
            || this._bufferQueue[0]?.start_token !== block.start_token
        ) {
            if (this._standbyBlock?.start_token === block.start_token) {
                this._standbyBlock = null;
                this._standbyReady = false;
            }
            return false;
        }
        this._ensureBlockTimings(block, this._standbyAudio);
        this._standbyReady = true;
        this._notifyBuffer();
        return true;
    }

    async _fillBuffer(generation = this._generation) {
        const cur = this._currentBlock;
        if (!cur || !this._isCurrent(generation)) return;
        if (this._bufferFillPromise && this._bufferFillGeneration === generation) {
            return this._bufferFillPromise;
        }

        const run = (async () => {
            if (this._bufferQueue.length && !this._standbyReady) {
                await this._primeStandby(generation);
            }
            let next = this._bufferQueue.length
                ? this._bufferQueue[this._bufferQueue.length - 1].end_token
                : cur.end_token;
            while (
                this._isCurrent(generation)
                && this._bufferQueue.length < this._maxBufferedBlocks
                && this._bufferedSeconds() < this._bufferTargetSeconds
                && next < this._totalTokens()
            ) {
                const block = await this._fetchBlock(next, generation, { reportErrors: false });
                if (!block || !this._isCurrent(generation)) return;
                if (block.end_token <= next) {
                    this._onError("O servidor retornou um bloco de narração inválido.");
                    return;
                }
                if (!this._bufferQueue.some((item) => item.start_token === block.start_token)) {
                    this._bufferQueue.push(block);
                    this._notifyBuffer();
                }
                if (this._bufferQueue.length === 1) {
                    await this._primeStandby(generation);
                }
                next = block.end_token;
            }
        })();
        this._bufferFillPromise = run;
        this._bufferFillGeneration = generation;
        try {
            await run;
        } finally {
            if (this._bufferFillPromise === run) {
                this._bufferFillPromise = null;
                this._bufferFillGeneration = null;
            }
        }
    }

    _promoteStandby(next, generation) {
        if (
            !this._standbyReady
            || !this._standbyBlock
            || this._standbyBlock.start_token !== next
            || !this._isCurrent(generation)
        ) {
            return null;
        }
        this._stopClock();
        const previousAudio = this._audio;
        this._audio = this._standbyAudio;
        this._standbyAudio = previousAudio;
        const block = this._standbyBlock;
        this._currentBlock = block;
        this._bufferQueue.shift();
        this._standbyBlock = null;
        this._standbyReady = false;
        this._releaseAudio(this._standbyAudio);
        this._applyRate(this._audio);
        this._ensureBlockTimings(block, this._audio);
        this._recordBlockMetrics(block, this._audio);
        this._onBlockChange(block);
        this._notifyBuffer();
        return block;
    }

    async _onEnded(event) {
        if (event?.target && event.target !== this._audio) return;
        const generation = this._generation;
        // Whole document finished?
        const cur = this._currentBlock;
        const next = cur ? cur.end_token : this._totalTokens();
        if (next >= this._totalTokens()) {
            this._playing = false;
            this._loading = false;
            this._stopClock();
            this._notifyState();
            this._onEnd();
            return;
        }
        this._setLoading(true);
        if (!this._standbyReady) await this._fillBuffer(generation);
        let block = this._promoteStandby(next, generation);
        if (!block) block = await this._loadBlockForToken(next, generation);
        if (!block) {
            if (this._isCurrent(generation)) this.pause();
            return;
        }
        this._audio.currentTime = 0;
        this._lastIdx = -1;
        if (this._playing) {
            try {
                this._applyRate(this._audio);
                await this._audio.play();
            } catch (_) {
                if (this._isCurrent(generation)) {
                    this._playing = false;
                    this._onError("Não foi possível continuar o áudio.");
                }
            }
            if (!this._isCurrent(generation)) {
                this._audio.pause();
                return;
            }
            if (this._isCurrent(generation) && this._playing) {
                this._startClock();
                this._fillBuffer(generation);
            }
        }
        if (this._isCurrent(generation)) this._setLoading(false);
    }

    // Start (or resume) playback from the engine's current pointer.
    async play() {
        if (this._playing || this._loading || !this._engine) return;
        const generation = this._invalidateAsync();
        this._setLoading(true);
        const tokenIdx = this._engine.pointer;
        const block = await this._loadBlockForToken(tokenIdx, generation);
        if (!block) {
            if (this._isCurrent(generation)) this._setLoading(false);
            return;
        }
        this._seekAudioToToken(block, tokenIdx);
        this._playing = true;
        try {
            this._applyRate(this._audio);
            await this._audio.play();
        } catch (e) {
            if (!this._isCurrent(generation)) return;
            this._playing = false;
            this._loading = false;
            this._onError("Não foi possível iniciar o áudio.");
            this._notifyState();
            return;
        }
        if (!this._isCurrent(generation)) {
            this._audio.pause();
            return;
        }
        this._loading = false;
        this._startClock();
        this._fillBuffer(generation);
        this._notifyState();
    }

    pause() {
        this._invalidateAsync();
        this._playing = false;
        this._loading = false;
        this._audio.pause();
        this._stopClock();
        this._notifyState();
    }

    async toggle() {
        if (this._playing || this._loading) this.pause();
        else await this.play();
    }

    // External jump (TOC, scrubber, click-to-jump) while TTS is the driver.
    async seek(tokenIdx) {
        const wasPlaying = this._playing;
        const generation = this._invalidateAsync();
        this._audio.pause();
        this._stopClock();
        this._playing = wasPlaying;
        this._setLoading(true);
        const block = await this._loadBlockForToken(tokenIdx, generation);
        if (!block) {
            if (this._isCurrent(generation)) {
                this._playing = false;
                this._setLoading(false);
            }
            return;
        }
        this._seekAudioToToken(block, tokenIdx);
        if (this._engine) this._engine.syncToIndex(tokenIdx);
        if (wasPlaying) {
            try {
                this._applyRate(this._audio);
                await this._audio.play();
            } catch (_) {
                if (this._isCurrent(generation)) {
                    this._playing = false;
                    this._onError("Não foi possível retomar o áudio após navegar.");
                }
            }
            if (!this._isCurrent(generation)) {
                this._audio.pause();
                return;
            }
            if (this._isCurrent(generation) && this._playing) {
                this._startClock();
                this._fillBuffer(generation);
            }
        } else {
            this._fillBuffer(generation);
        }
        if (this._isCurrent(generation)) {
            this._loading = false;
            this._notifyState();
        }
    }

    // Fully stop and release (leaving the reader, disabling TTS, doc change).
    stop() {
        this._invalidateAsync();
        this._playing = false;
        this._loading = false;
        this._audio.pause();
        this._standbyAudio.pause();
        this._stopClock();
        this._releaseAudio(this._audio);
        this._currentBlock = null;
        this._clearBuffer();
        this._metricSamples = [];
        this._lastIdx = -1;
        this._notifyMetrics();
        this._notifyState();
    }

    // Stronger lifecycle boundary used when no reader document remains.
    // Unlike stop(), this also releases callbacks and document references;
    // configure() establishes a fresh context when the next document opens.
    reset() {
        this.stop();
        this._engine = null;
        this._apiFetch = null;
        this._docId = null;
        this._currentBlock = null;
        this._prefetched = null;
        this._onError = () => {};
        this._onEnd = () => {};
        this._onStateChange = () => {};
        this._onBlockChange = () => {};
        this._onMetricsChange = () => {};
        this._onBufferChange = () => {};
    }
}
