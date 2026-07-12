// RSVP tokenizer + micro-pause weighting + playback engine.
// This is the core of the reading feel — the weighting here is deliberately
// tuned so long words, punctuation and paragraph breaks slow the flash down
// instead of flying past at a constant per-word rate.

function computeWeight(word) {
    let weight = 1.0;
    const letters = word.replace(/[^\p{L}\p{N}]/gu, "");

    if (letters.length >= 8 || /\d/.test(letters)) {
        weight += 0.5;
    }
    if (/[,;:]$/.test(word)) {
        weight += 0.35;
    }
    if (/[.!?]["')\]]?$/.test(word)) {
        weight += 0.9;
    }
    return weight;
}

export function tokenize(text) {
    const paragraphs = text
        .replace(/\r\n/g, "\n")
        .split(/\n\s*\n/)
        .map((p) => p.trim())
        .filter((p) => p.length > 0);

    const tokens = [];
    paragraphs.forEach((paragraph, pIndex) => {
        const words = paragraph.split(/\s+/).filter((w) => w.length > 0);
        words.forEach((word, wIndex) => {
            const isLastInParagraph = wIndex === words.length - 1;
            tokens.push({
                text: word,
                weight: computeWeight(word),
                paragraphEnd: isLastInParagraph && pIndex < paragraphs.length - 1,
            });
        });
    });
    return tokens;
}

function chunkWeight(chunkTokens) {
    return chunkTokens.reduce(
        (sum, t) => sum + t.weight + (t.paragraphEnd ? 1.2 : 0),
        0
    );
}

export class RSVPEngine {
    constructor({ onChunk, onProgress, onEnd }) {
        this.tokens = [];
        this.pointer = 0;
        this.wpm = 300;
        this.chunkSize = 1;
        this.playing = false;
        this.timer = null;
        this.onChunk = onChunk || (() => {});
        this.onProgress = onProgress || (() => {});
        this.onEnd = onEnd || (() => {});
    }

    load(text) {
        this.pause();
        this.tokens = tokenize(text);
        this.pointer = 0;
        this._render();
    }

    setWpm(wpm) {
        this.wpm = Math.max(100, Math.min(1000, wpm));
    }

    setChunkSize(size) {
        this.chunkSize = Math.max(1, Math.min(4, size));
    }

    play() {
        if (this.playing || this.tokens.length === 0) return;
        if (this.pointer >= this.tokens.length) this.pointer = 0;
        this.playing = true;
        this._tick();
    }

    pause() {
        this.playing = false;
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
    }

    toggle() {
        if (this.playing) this.pause();
        else this.play();
    }

    rewind() {
        this.pause();
        this.pointer = Math.max(0, this.pointer - this.chunkSize);
        this._render();
    }

    forward() {
        this.pause();
        this.pointer = Math.min(
            Math.max(0, this.tokens.length - 1),
            this.pointer + this.chunkSize
        );
        this._render();
    }

    seekFraction(fraction) {
        this.pause();
        const idx = Math.floor(fraction * this.tokens.length);
        this.pointer = Math.max(0, Math.min(this.tokens.length - 1, idx));
        this._render();
    }

    _currentChunk() {
        return this.tokens.slice(this.pointer, this.pointer + this.chunkSize);
    }

    _render() {
        const chunk = this._currentChunk();
        this.onChunk(chunk);
        this.onProgress(this.tokens.length ? this.pointer / this.tokens.length : 0);
    }

    _tick() {
        if (!this.playing) return;
        const chunk = this._currentChunk();
        if (chunk.length === 0) {
            this.playing = false;
            this.onEnd();
            return;
        }
        this.onChunk(chunk);
        this.onProgress(this.pointer / this.tokens.length);

        const baseMsPerWord = 60000 / this.wpm;
        const delay = baseMsPerWord * chunkWeight(chunk);

        this.timer = setTimeout(() => {
            this.pointer += chunk.length;
            this._tick();
        }, delay);
    }
}
