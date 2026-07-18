"""TTS core (Fase 8): canonical block segmentation, a Python tokenizer that
mirrors the JS one, the Kokoro-FastAPI client, and fuzzy time-alignment.

The single load-bearing invariant here is **tokenizer parity**: the global
token indices produced by `tokenize()` below must match, one-for-one, the
indices produced by `tokenize()` in `static/js/rsvp.js`. The frontend asks for
a block by a global token index (its `engine.pointer`), and the timestamps we
return are keyed by that same global index. If the two tokenizers diverge, the
karaoke highlight lands on the wrong word. Both split paragraphs on a blank
line and words on runs of whitespace, and share the same sentence-end regex.
"""

import base64
import binascii
import difflib
import json
import logging
import math
import os
import random
import re
import threading
import time
import unicodedata
from urllib.parse import urlparse

import httpx

# --- Kokoro service configuration -------------------------------------------
# Overridable by env so the Docker deploy can point at the stack's service name
# (e.g. http://kokoro:8880) while local dev hits the published port.
KOKORO_URL = os.environ.get("KOKORO_URL", "http://localhost:8880").rstrip("/")
DEFAULT_VOICE = os.environ.get("KOKORO_VOICE", "pf_dora")  # Brazilian-PT female
# Part of the canonical-block UNIQUE key. Bump if the engine/voice model changes
# in a way that should invalidate previously generated audio.
# The block policy is part of cache compatibility too: the b250 suffix keeps
# older 260-token rows from being reused after the hard-ceiling correction.
MODEL_VERSION = "kokoro-82m-b250-r2"
AUDIO_FORMAT = "mp3"
AUDIO_MEDIA_TYPE = "audio/mpeg"

# Outbound safety limits. The canonical token ceiling protects normal input,
# while MAX_INPUT_CHARS also covers the pathological case of one enormous
# whitespace-free token. Response limits keep a malformed/upstream response
# from turning into an unbounded Base64/JSON allocation in the FastAPI worker.
MAX_INPUT_CHARS = int(os.environ.get("KOKORO_MAX_INPUT_CHARS", "4000"))
MAX_AUDIO_BYTES = int(os.environ.get("KOKORO_MAX_AUDIO_BYTES", str(16 * 1024 * 1024)))
MAX_NDJSON_LINE_BYTES = int(
    os.environ.get("KOKORO_MAX_NDJSON_LINE_BYTES", str(8 * 1024 * 1024))
)
MAX_TIMESTAMPS = int(os.environ.get("KOKORO_MAX_TIMESTAMPS", "4096"))
MAX_VOICE_RESPONSE_BYTES = 256 * 1024
MAX_DISCOVERED_VOICES = 512
VOICE_CACHE_SECONDS = 300.0
VOICE_FAILURE_CACHE_SECONDS = float(os.environ.get("KOKORO_FAILURE_CACHE_SECONDS", "10"))

_HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
_HTTP_LIMITS = httpx.Limits(max_connections=2, max_keepalive_connections=1)
_logger = logging.getLogger(__name__)


class KokoroError(RuntimeError):
    """Base class for failures already classified by the Kokoro adapter."""


class KokoroProtocolError(KokoroError):
    """Kokoro returned a malformed, unsafe, or internally inconsistent body."""


class KokoroUnavailableError(KokoroError):
    """Kokoro failed completely, including the stable audio-only fallback."""


class KokoroCircuitOpenError(KokoroUnavailableError):
    """Requests are paused briefly after repeated complete upstream failures."""


_circuit_lock = threading.Lock()
_circuit_failures = 0
_circuit_open_until = 0.0
_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_COOLDOWN_SECONDS = 30.0

_voice_cache_lock = threading.Lock()
_voice_cache: list[str] = []
_voice_cache_until = 0.0
_voice_cache_available: bool | None = None
_voice_cache_reason: str | None = None
_voice_cache_retry_after: int | None = None

# Block sizing — identical to the frontend's flowBlocks (FLOW_BLOCK_SOFT/HARD)
# so a TTS block and a Flow block cover the same span. A block closes at a
# paragraph end, or once it is long enough and hits a sentence end, or at a
# hard ceiling regardless — never an unbounded wall of text.
BLOCK_SOFT = 200
BLOCK_HARD = 250

_SENTENCE_END = re.compile(r'[.!?]["\')\]]?$')
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_WHITESPACE = re.compile(r"\s+")


def _validated_kokoro_url() -> str:
    parsed = urlparse(KOKORO_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise KokoroProtocolError("KOKORO_URL deve ser uma URL HTTP(S) válida.")
    if parsed.username or parsed.password:
        raise KokoroProtocolError("KOKORO_URL não pode conter credenciais embutidas.")
    return KOKORO_URL


def sanitize_tts_text(text: str) -> str:
    """Normalize a document block before it crosses the service boundary.

    Content stays plain text: control characters are converted to whitespace,
    Unicode is normalized, and a second independent character ceiling protects
    Kokoro even if a document contains a single gigantic token.
    """
    normalized = unicodedata.normalize("NFC", str(text or ""))
    normalized = "".join(
        " " if unicodedata.category(ch) == "Cc" else ch for ch in normalized
    )
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    if not normalized:
        raise ValueError("Bloco de narração vazio após normalização.")
    if len(normalized) > MAX_INPUT_CHARS:
        raise ValueError(
            f"Bloco de narração excede o limite seguro de {MAX_INPUT_CHARS} caracteres."
        )
    return normalized


def _ends_sentence(word: str) -> bool:
    return bool(_SENTENCE_END.search(word))


def tokenize(text: str) -> list[dict]:
    """Mirror of `tokenize()` in rsvp.js. Returns tokens in reading order with
    the flags the segmenter needs. Index in the list == global token index."""
    text = text.replace("\r\n", "\n")
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text)]
    paragraphs = [p for p in paragraphs if p]

    tokens: list[dict] = []
    for p_index, paragraph in enumerate(paragraphs):
        words = [w for w in _WHITESPACE.split(paragraph) if w]
        for w_index, word in enumerate(words):
            tokens.append(
                {
                    "text": word,
                    "sentence_end": _ends_sentence(word),
                    "paragraph_end": w_index == len(words) - 1
                    and p_index < len(paragraphs) - 1,
                }
            )
    return tokens


def canonical_blocks(tokens: list[dict]) -> list[tuple[int, int]]:
    """Deterministically segment the whole token list into [start, end) blocks.
    Deterministic is the point: any token maps to exactly one block with fixed
    bounds, so `POST /tts/blocks` is idempotent regardless of which token in the
    block was requested."""
    blocks: list[tuple[int, int]] = []
    start = 0
    count = 0
    for idx, token in enumerate(tokens):
        count += 1
        soft_break = count >= BLOCK_SOFT and token["sentence_end"]
        if token["paragraph_end"] or soft_break or count >= BLOCK_HARD:
            blocks.append((start, idx + 1))
            start = idx + 1
            count = 0
    if start < len(tokens) or not blocks:
        blocks.append((start, len(tokens)))
    return blocks


def block_for_token(blocks: list[tuple[int, int]], token_idx: int) -> tuple[int, int]:
    lo, hi = 0, len(blocks) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end = blocks[mid]
        if token_idx < start:
            hi = mid - 1
        elif token_idx >= end:
            lo = mid + 1
        else:
            return blocks[mid]
    return blocks[-1] if blocks else (0, 0)


# --- Kokoro client -----------------------------------------------------------


def _extract_upstream_detail(response: httpx.Response) -> str:
    """Return a short log-only explanation without reflecting arbitrary HTML."""
    try:
        body = response.json()
        detail = body.get("detail", body) if isinstance(body, dict) else body
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("error") or detail
        value = str(detail)
    except Exception:
        value = response.text or response.reason_phrase
    return _WHITESPACE.sub(" ", value).strip()[:400]


def _parse_timestamp(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    word = raw.get("word") or raw.get("text") or ""
    if not isinstance(word, str) or not word.strip():
        return None
    try:
        start = float(raw.get("start_time", raw.get("start", 0.0)))
        end = float(raw.get("end_time", raw.get("end", start)))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(start) or not math.isfinite(end):
        return None
    start = max(0.0, start)
    end = max(start, end)
    return {"word": word, "start": start, "end": end}


def decode_captioned_lines(lines) -> tuple[bytes, list[dict]]:
    """Aggregate Kokoro's streaming NDJSON without its buggy AudioChunk.combine.

    Kokoro v0.6 can legitimately emit a generated audio fragment with
    ``timestamps: null``. The non-streaming upstream code attempts ``list +=
    None`` and returns HTTP 500; here that fragment's audio is retained and the
    missing timing span is handled later by our alignment fallback.
    """
    audio_parts: list[bytes] = []
    words: list[dict] = []
    audio_size = 0

    for raw_line in lines:
        if isinstance(raw_line, bytes):
            if len(raw_line) > MAX_NDJSON_LINE_BYTES:
                raise KokoroProtocolError("Linha NDJSON do Kokoro excedeu o limite seguro.")
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise KokoroProtocolError("NDJSON do Kokoro não está em UTF-8.") from exc
        else:
            line = str(raw_line)
            if len(line.encode("utf-8")) > MAX_NDJSON_LINE_BYTES:
                raise KokoroProtocolError("Linha NDJSON do Kokoro excedeu o limite seguro.")
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise KokoroProtocolError("Kokoro retornou NDJSON inválido.") from exc
        if not isinstance(data, dict):
            raise KokoroProtocolError("Fragmento NDJSON do Kokoro não é um objeto.")

        encoded = data.get("audio") or data.get("audio_base64") or ""
        if encoded:
            if not isinstance(encoded, str):
                raise KokoroProtocolError("Campo de áudio do Kokoro não é Base64 textual.")
            try:
                chunk = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise KokoroProtocolError("Kokoro retornou áudio Base64 inválido.") from exc
            audio_size += len(chunk)
            if audio_size > MAX_AUDIO_BYTES:
                raise KokoroProtocolError("Áudio do Kokoro excedeu o limite seguro por bloco.")
            if chunk:
                audio_parts.append(chunk)

        raw_words = data.get("timestamps", data.get("words"))
        # Missing timestamps are the exact upstream v0.6 regression. They do
        # not invalidate the audio that was successfully generated.
        if raw_words is None:
            continue
        if not isinstance(raw_words, list):
            raise KokoroProtocolError("Campo de timestamps do Kokoro não é uma lista.")
        chunk_words = [entry for item in raw_words if (entry := _parse_timestamp(item))]
        if words and chunk_words and chunk_words[0]["start"] < words[-1]["end"]:
            # Some releases reset each streaming fragment's clock to zero;
            # convert those entries to the aggregate audio timeline.
            offset = words[-1]["end"]
            for entry in chunk_words:
                entry["start"] += offset
                entry["end"] += offset
        words.extend(chunk_words)
        if len(words) > MAX_TIMESTAMPS:
            raise KokoroProtocolError("Kokoro retornou timestamps demais para um bloco.")

    return b"".join(audio_parts), words


def _captioned_speech(client: httpx.Client, text: str, voice: str) -> tuple[bytes, list[dict]]:
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": AUDIO_FORMAT,
        "speed": 1.0,
        # Streaming bypasses the upstream AudioChunk.combine(None) defect and
        # lets this adapter enforce strict per-line and aggregate limits.
        "stream": True,
        "return_timestamps": True,
        "normalization_options": {"normalize": False},
    }
    with client.stream(
        "POST", f"{_validated_kokoro_url()}/dev/captioned_speech", json=payload
    ) as response:
        if response.is_error:
            detail = _extract_upstream_detail(response)
            _logger.warning(
                "Kokoro captioned_speech HTTP %s: %s", response.status_code, detail
            )
            response.raise_for_status()
        return decode_captioned_lines(response.iter_lines())


def _audio_only_speech(client: httpx.Client, text: str, voice: str) -> bytes:
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": AUDIO_FORMAT,
        "speed": 1.0,
        "normalization_options": {"normalize": False},
    }
    parts: list[bytes] = []
    size = 0
    with client.stream(
        "POST", f"{_validated_kokoro_url()}/v1/audio/speech", json=payload
    ) as response:
        if response.is_error:
            detail = _extract_upstream_detail(response)
            _logger.warning(
                "Kokoro audio-only HTTP %s: %s", response.status_code, detail
            )
            response.raise_for_status()
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_AUDIO_BYTES:
                raise KokoroProtocolError("Áudio de fallback excedeu o limite seguro por bloco.")
            if chunk:
                parts.append(chunk)
    audio = b"".join(parts)
    if not audio:
        raise KokoroProtocolError("Kokoro não retornou áudio no fallback estável.")
    return audio


def _check_circuit() -> None:
    with _circuit_lock:
        remaining = _circuit_open_until - time.monotonic()
    if remaining > 0:
        raise KokoroCircuitOpenError(
            f"Kokoro temporariamente protegido após falhas repetidas; tente em {math.ceil(remaining)}s."
        )


def _record_circuit_success() -> None:
    global _circuit_failures, _circuit_open_until
    with _circuit_lock:
        _circuit_failures = 0
        _circuit_open_until = 0.0


def _record_circuit_failure() -> None:
    global _circuit_failures, _circuit_open_until
    with _circuit_lock:
        _circuit_failures += 1
        if _circuit_failures >= _CIRCUIT_FAILURE_THRESHOLD:
            _circuit_open_until = time.monotonic() + _CIRCUIT_COOLDOWN_SECONDS


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {
        502,
        503,
        504,
    }


def call_kokoro(text: str, voice: str) -> tuple[bytes, list[dict]]:
    """Generate a safe canonical block with captioned then audio-only fallback.

    Caption failures are not blindly replayed: the known deterministic HTTP
    500 falls through to the stable OpenAI-compatible audio route. Only that
    fallback gets one bounded retry for genuinely transient transport/5xx
    conditions. A complete failure contributes to a short circuit breaker.
    """
    safe_text = sanitize_tts_text(text)
    _check_circuit()
    caption_error: Exception | None = None

    with httpx.Client(
        timeout=_HTTP_TIMEOUT,
        limits=_HTTP_LIMITS,
        follow_redirects=False,
    ) as client:
        try:
            audio, words = _captioned_speech(client, safe_text, voice)
            if not audio:
                raise KokoroProtocolError("Kokoro não retornou áudio legendado.")
            _record_circuit_success()
            return audio, words
        except Exception as exc:
            caption_error = exc
            _logger.warning(
                "Falha no caminho legendado do Kokoro; usando fallback de áudio: %s",
                exc,
            )

        fallback_error: Exception | None = None
        for attempt in range(2):
            try:
                audio = _audio_only_speech(client, safe_text, voice)
                _record_circuit_success()
                return audio, []
            except Exception as exc:
                fallback_error = exc
                if attempt == 0 and _is_transient(exc):
                    time.sleep(0.2 + random.random() * 0.15)
                    continue
                break

    _record_circuit_failure()
    _logger.error(
        "Kokoro falhou nos caminhos legendado e estável: caption=%r fallback=%r",
        caption_error,
        fallback_error,
    )
    raise KokoroUnavailableError(
        "Kokoro não conseguiu produzir um bloco de áudio válido."
    ) from fallback_error


def _circuit_retry_after() -> int | None:
    with _circuit_lock:
        remaining = _circuit_open_until - time.monotonic()
    return max(1, math.ceil(remaining)) if remaining > 0 else None


def _voice_failure_message(exc: Exception) -> tuple[str, int]:
    if isinstance(exc, KokoroCircuitOpenError):
        return "Narrador em recuperação após falhas repetidas.", _circuit_retry_after() or 5
    if isinstance(exc, httpx.ConnectError):
        return "Servidor de narração local não está ativo.", 5
    if isinstance(exc, httpx.TimeoutException):
        return "Servidor de narração local não respondeu a tempo.", 5
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Servidor de narração respondeu HTTP {exc.response.status_code}.", 5
    return "Servidor de narração retornou uma resposta inválida.", 5


def fetch_voice_status(*, force: bool = False) -> dict[str, object]:
    global _voice_cache, _voice_cache_until
    global _voice_cache_available, _voice_cache_reason, _voice_cache_retry_after
    now = time.monotonic()
    with _voice_cache_lock:
        if not force and _voice_cache_available is not None and now < _voice_cache_until:
            return {
                "voices": list(_voice_cache),
                "available": _voice_cache_available,
                "reason": _voice_cache_reason,
                "retry_after": _voice_cache_retry_after,
            }
    try:
        _check_circuit()
        with httpx.Client(
            timeout=httpx.Timeout(connect=1.5, read=3.0, write=3.0, pool=1.5),
            limits=_HTTP_LIMITS,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            with client.stream(
                "GET", f"{_validated_kokoro_url()}/v1/audio/voices"
            ) as resp:
                resp.raise_for_status()
                body = bytearray()
                for chunk in resp.iter_bytes():
                    if len(body) + len(chunk) > MAX_VOICE_RESPONSE_BYTES:
                        raise KokoroProtocolError("Lista de vozes excedeu o limite seguro.")
                    body.extend(chunk)
            data = json.loads(body.decode("utf-8"))
        voices = data.get("voices") if isinstance(data, dict) else data
        if not isinstance(voices, list):
            raise KokoroProtocolError("Lista de vozes ausente.")
        # Kokoro-FastAPI v0.6 returns [{"id": "pf_dora", ...}], while older
        # releases returned a flat string list. Accept both contracts so voice
        # discovery remains compatible across the pinned runtime and old installs.
        result: list[str] = []
        for voice in voices:
            if isinstance(voice, str):
                voice_id = voice
            elif isinstance(voice, dict):
                voice_id = voice.get("id")
            else:
                voice_id = None
            if (
                isinstance(voice_id, str)
                and 0 < len(voice_id) <= 80
                and re.fullmatch(r"[A-Za-z0-9_-]+", voice_id)
            ):
                result.append(voice_id)
        result = sorted(set(result))[:MAX_DISCOVERED_VOICES]
        if not result:
            raise KokoroProtocolError("Nenhuma voz disponível.")
    except Exception as exc:
        reason, retry_after = _voice_failure_message(exc)
        _logger.info("Descoberta de vozes indisponível: %s", type(exc).__name__)
        with _voice_cache_lock:
            stale_voices = list(_voice_cache)
            _voice_cache_available = False
            _voice_cache_reason = reason
            _voice_cache_retry_after = retry_after
            _voice_cache_until = time.monotonic() + VOICE_FAILURE_CACHE_SECONDS
        return {
            "voices": stale_voices,
            "available": False,
            "reason": reason,
            "retry_after": retry_after,
        }
    with _voice_cache_lock:
        _voice_cache = result
        _voice_cache_available = True
        _voice_cache_reason = None
        _voice_cache_retry_after = None
        _voice_cache_until = time.monotonic() + VOICE_CACHE_SECONDS
    return {
        "voices": list(result),
        "available": True,
        "reason": None,
        "retry_after": None,
    }


def fetch_voices(*, force: bool = False) -> list[str]:
    """List voices Kokoro offers, using a bounded best-effort TTL cache."""
    return list(fetch_voice_status(force=force)["voices"])

# --- Fuzzy alignment ---------------------------------------------------------


def align_words(
    our_words: list[str], start_global: int, kokoro_words: list[dict]
) -> tuple[list[dict], float]:
    """Map Kokoro's per-word timings onto OUR tokens by non-whitespace char
    offset, so a punctuation/contraction split on either side doesn't shift the
    whole block. Returns (timestamps, alignment_score) where each timestamp is
    {"idx": global_token_index, "start": sec, "end": sec} and the score is the
    fraction of our tokens that received a real timing (coverage)."""
    # Our tokens -> flat lowercased non-space chars, remembering which global
    # token each char came from.
    our_chars: list[str] = []
    our_char_token: list[int] = []
    for local_i, word in enumerate(our_words):
        for ch in word:
            if ch.isspace():
                continue
            our_chars.append(ch.lower())
            our_char_token.append(start_global + local_i)

    # Kokoro words -> flat lowercased non-space chars, remembering each char's
    # (start, end) time.
    kok_chars: list[str] = []
    kok_char_time: list[tuple[float, float]] = []
    for kw in kokoro_words:
        for ch in kw["word"]:
            if ch.isspace():
                continue
            kok_chars.append(ch.lower())
            kok_char_time.append((kw["start"], kw["end"]))

    token_times: dict[int, list[tuple[float, float]]] = {}
    if our_chars and kok_chars:
        matcher = difflib.SequenceMatcher(a=our_chars, b=kok_chars, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "delete":
                continue  # our chars with no Kokoro counterpart (interpolated below)
            span = j2 - j1
            for k in range(i1, i2):
                if tag == "equal":
                    jk = j1 + (k - i1)
                elif span > 0:
                    jk = j1 + (k - i1) * span // max(1, i2 - i1)
                    jk = min(j2 - 1, max(j1, jk))
                else:
                    continue
                if 0 <= jk < len(kok_char_time):
                    token_times.setdefault(our_char_token[k], []).append(kok_char_time[jk])

    timestamps: list[dict] = []
    covered = 0
    last_end = 0.0
    for local_i in range(len(our_words)):
        g = start_global + local_i
        times = token_times.get(g)
        if times:
            start = min(t[0] for t in times)
            end = max(t[1] for t in times)
            covered += 1
        else:
            # Unaligned token (e.g. pure punctuation Kokoro didn't voice) —
            # collapse it onto the previous end so playback never jumps back.
            start = end = last_end
        start = max(start, last_end)  # enforce monotonic non-decreasing time
        end = max(end, start)
        last_end = end
        timestamps.append({"idx": g, "start": round(start, 3), "end": round(end, 3)})

    score = covered / len(our_words) if our_words else 0.0
    return timestamps, score
