// RSVP tokenizer + micro-pause weighting + playback engine.
// This is the core of the reading feel — the weighting here is deliberately
// tuned so long words, punctuation and paragraph breaks slow the flash down
// instead of flying past at a constant per-word rate.

function endsSentence(word) {
    return /[.!?]["')\]]?$/.test(word);
}

function computeWeight(word) {
    let weight = 1.0;
    const letters = word.replace(/[^\p{L}\p{N}]/gu, "");

    if (letters.length >= 8 || /\d/.test(letters)) {
        weight += 0.5;
    }
    if (/[,;:]$/.test(word)) {
        weight += 0.35;
    }
    if (endsSentence(word)) {
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
                sentenceEnd: endsSentence(word),
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
        // Average per-word weight of the loaded document — dividing each
        // chunk's weight by this normalizes throughput so `wpm` means real
        // words/minute instead of a nominal pre-pause rate.
        this.avgWeight = 1;
        this.onChunk = onChunk || (() => {});
        this.onProgress = onProgress || (() => {});
        this.onEnd = onEnd || (() => {});
    }

    load(text) {
        this.pause();
        this.tokens = tokenize(text);
        this.pointer = 0;
        this.avgWeight = this.tokens.length
            ? chunkWeight(this.tokens) / this.tokens.length
            : 1;
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

    // Sentence, not word/chunk, is the logical unit for manual navigation —
    // it's what a reader actually wants to jump back/forward to.
    _sentenceStart(fromIndex) {
        let i = fromIndex;
        while (i > 0 && !this.tokens[i - 1].sentenceEnd) {
            i--;
        }
        return i;
    }

    _sentenceEndIndex(fromIndex) {
        let i = fromIndex;
        while (i < this.tokens.length - 1 && !this.tokens[i].sentenceEnd) {
            i++;
        }
        return i;
    }

    rewind() {
        this.pause();
        const currentStart = this._sentenceStart(this.pointer);
        if (currentStart < this.pointer) {
            // Mid-sentence: jump to the start of this sentence first.
            this.pointer = currentStart;
        } else if (currentStart > 0) {
            // Already at a sentence start: jump to the previous sentence's start.
            this.pointer = this._sentenceStart(currentStart - 1);
        } else {
            this.pointer = 0;
        }
        this._render();
    }

    forward() {
        this.pause();
        const endIdx = this._sentenceEndIndex(this.pointer);
        this.pointer = Math.min(Math.max(0, this.tokens.length - 1), endIdx + 1);
        this._render();
    }

    seekFraction(fraction) {
        this.pause();
        const idx = Math.floor(fraction * this.tokens.length);
        this.pointer = Math.max(0, Math.min(this.tokens.length - 1, idx));
        this._render();
    }

    _currentChunk() {
        const chunk = [];
        for (
            let i = this.pointer;
            i < this.tokens.length && chunk.length < this.chunkSize;
            i++
        ) {
            const token = this.tokens[i];
            chunk.push(token);
            // Never flash past a paragraph or sentence boundary together with
            // the next one — the eye needs that beat to land as a real pause.
            if (token.paragraphEnd || token.sentenceEnd) break;
        }
        return chunk;
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
        const delay = baseMsPerWord * (chunkWeight(chunk) / this.avgWeight);

        this.timer = setTimeout(() => {
            this.pointer += chunk.length;
            this._tick();
        }, delay);
    }
}
