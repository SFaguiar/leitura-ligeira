"""Fase 8 — TTS endpoints.

Design constraints baked in here (from the deliberated plan):
- **Short transaction:** the SQLite connection is opened only to read the
  document text and (separately) to write the row. It is CLOSED before the
  slow Kokoro/GPU call, so audio generation never holds a DB lock and stalls
  concurrent heartbeat writes / the WAL checkpoint.
- **Idempotent + single-flight:** the canonical block is deterministic, its
  (document, start, voice, model) tuple is UNIQUE, and an in-memory lock per
  tuple stops two simultaneous requests from both hitting the GPU.
- **Atomic file:** audio is written to a `.part` file and renamed, so a reader
  never sees a half-written block.
- **Authenticated audio:** served via a route that reuses
  `_get_visible_document` — never via StaticFiles — so a private document's
  narration is as protected as its text.
"""

import hashlib
import json
import logging
import re
import threading

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app import tts
from app.auth import get_current_user
from app.database import DB_PATH, get_connection
from app.routers.documents import _get_visible_document, _iso_now
from app.schemas import TtsBlockDetail, TtsBlockRequest, TtsVoices

router = APIRouter()

TTS_DIR = DB_PATH.parent / "tts"

# One lock per canonical block key, so two concurrent requests for the same
# block serialize instead of both generating. The dict itself is guarded by
# _locks_guard. In-memory is enough — single home instance, no multi-worker.
_locks: dict[tuple, threading.Lock] = {}
_locks_guard = threading.Lock()

# A single RTX 5060 Ti serves this local instance. Different canonical block
# locks prevent duplicate work, while this global gate prevents distinct
# documents/tabs from launching simultaneous model inference and fragmenting
# the 8 GB VRAM pool. Waiting is bounded so an abandoned request cannot hold
# every FastAPI worker forever.
_generation_gate = threading.BoundedSemaphore(1)
_GENERATION_WAIT_SECONDS = 30.0
_logger = logging.getLogger(__name__)


def _lock_for(key: tuple) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def _audio_url(document_id: int, block_id: int) -> str:
    return f"/documents/{document_id}/tts/blocks/{block_id}/audio"


def _row_to_detail(row) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "start_token": row["start_token"],
        "end_token": row["end_token"],
        "voice": row["voice"],
        "model_version": row["model_version"],
        "alignment_score": row["alignment_score"],
        "audio_url": _audio_url(row["document_id"], row["id"]),
        "timestamps": json.loads(row["timestamps_json"]),
    }


def _find_block(conn, document_id: int, start_token: int, voice: str):
    return conn.execute(
        "SELECT * FROM tts_blocks "
        "WHERE document_id = ? AND start_token = ? AND voice = ? AND model_version = ?",
        (document_id, start_token, voice, tts.MODEL_VERSION),
    ).fetchone()


@router.get("/tts/voices", response_model=TtsVoices)
def list_voices(user: dict = Depends(get_current_user)):
    """Voices Kokoro offers, for the UI picker. Empty list if Kokoro is down —
    the frontend falls back to `default`."""
    return {"voices": tts.fetch_voices(), "default": tts.DEFAULT_VOICE}


@router.post("/documents/{document_id}/tts/blocks", response_model=TtsBlockDetail)
def create_tts_block(
    document_id: int,
    payload: TtsBlockRequest,
    user: dict = Depends(get_current_user),
):
    voice = (payload.voice or tts.DEFAULT_VOICE).strip() or tts.DEFAULT_VOICE
    if len(voice) > 80:
        raise HTTPException(status_code=422, detail="Identificador de voz muito longo.")
    available_voices = tts.fetch_voices()
    if not available_voices:
        raise HTTPException(
            status_code=503,
            detail="O serviço de narração não está pronto para validar as vozes.",
            headers={"Retry-After": "5"},
        )
    if voice not in available_voices:
        raise HTTPException(status_code=422, detail="Voz de narração não reconhecida.")

    # --- read text, then close the connection (no DB held during the GPU call)
    conn = get_connection()
    try:
        doc = _get_visible_document(conn, document_id, user)
        raw_text = doc["raw_text"] if doc else None
    finally:
        conn.close()
    if raw_text is None:
        raise HTTPException(status_code=404, detail="Document not found")

    tokens = tts.tokenize(raw_text)
    if not tokens:
        raise HTTPException(status_code=400, detail="Documento sem texto legível.")
    blocks = tts.canonical_blocks(tokens)
    token_idx = max(0, min(len(tokens) - 1, payload.token))
    start_token, end_token = tts.block_for_token(blocks, token_idx)

    # Fast path — already generated (idempotent).
    conn = get_connection()
    try:
        existing = _find_block(conn, document_id, start_token, voice)
    finally:
        conn.close()
    if existing:
        return _row_to_detail(existing)

    key = (document_id, start_token, voice, tts.MODEL_VERSION)
    with _lock_for(key):
        # Re-check under the lock: another request may have finished meanwhile.
        conn = get_connection()
        try:
            existing = _find_block(conn, document_id, start_token, voice)
        finally:
            conn.close()
        if existing:
            return _row_to_detail(existing)

        block_words = [t["text"] for t in tokens[start_token:end_token]]
        block_text = " ".join(block_words)
        try:
            block_text = tts.sanitize_tts_text(block_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if not _generation_gate.acquire(timeout=_GENERATION_WAIT_SECONDS):
            raise HTTPException(
                status_code=503,
                detail="O narrador está processando outro trecho. Tente novamente em instantes.",
                headers={"Retry-After": "3"},
            )
        try:
            try:
                audio, kokoro_words = tts.call_kokoro(block_text, voice)
            except tts.KokoroCircuitOpenError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=str(exc),
                    headers={"Retry-After": "30"},
                ) from exc
            except tts.KokoroUnavailableError as exc:
                _logger.exception("Kokoro falhou completamente ao gerar bloco")
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "O serviço de narração falhou nos caminhos legendado e de "
                        "áudio. O trecho não foi perdido; tente novamente."
                    ),
                ) from exc
            except httpx.ConnectError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Servidor Kokoro indisponível. Inicie o serviço TTS na porta 8880.",
                ) from exc
            except httpx.TimeoutException as exc:
                raise HTTPException(
                    status_code=504,
                    detail="O servidor Kokoro demorou demais para gerar o áudio.",
                ) from exc
            except Exception as exc:  # malformed/unexpected response — surface as 502
                _logger.exception("Falha inesperada no adaptador Kokoro")
                raise HTTPException(
                    status_code=502,
                    detail="O serviço de narração retornou uma resposta inválida.",
                ) from exc
        finally:
            _generation_gate.release()
        if not audio:
            raise HTTPException(status_code=502, detail="Kokoro não retornou áudio.")

        timestamps, score = tts.align_words(block_words, start_token, kokoro_words)

        TTS_DIR.mkdir(parents=True, exist_ok=True)
        # Voice comes from the request even though the UI normally submits a
        # discovered option. Keep it filename-safe and append a digest so two
        # different identifiers that sanitize equally can never share a file.
        safe_voice = re.sub(r"[^A-Za-z0-9._-]+", "_", voice).strip("._") or "voice"
        voice_digest = hashlib.sha256(voice.encode("utf-8")).hexdigest()[:12]
        safe_voice = safe_voice[:48]
        filename = f"{document_id}_{start_token}_{safe_voice}_{voice_digest}_{tts.MODEL_VERSION}.{tts.AUDIO_FORMAT}"
        final_path = TTS_DIR / filename
        tmp_path = final_path.with_name(final_path.name + ".part")
        tmp_path.write_bytes(audio)
        tmp_path.replace(final_path)  # atomic rename

        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO tts_blocks "
                "(document_id, start_token, end_token, voice, model_version, "
                " audio_path, timestamps_json, alignment_score, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document_id,
                    start_token,
                    end_token,
                    voice,
                    tts.MODEL_VERSION,
                    filename,
                    json.dumps(timestamps),
                    score,
                    _iso_now(),
                ),
            )
            conn.commit()
            row = _find_block(conn, document_id, start_token, voice)
        finally:
            conn.close()
    return _row_to_detail(row)


@router.get("/documents/{document_id}/tts/blocks/{block_id}/audio")
def get_tts_audio(
    document_id: int,
    block_id: int,
    user: dict = Depends(get_current_user),
):
    conn = get_connection()
    try:
        doc = _get_visible_document(conn, document_id, user)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        row = conn.execute(
            "SELECT audio_path FROM tts_blocks WHERE id = ? AND document_id = ?",
            (block_id, document_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Audio block not found")
    path = TTS_DIR / row["audio_path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing")
    return FileResponse(path, media_type=tts.AUDIO_MEDIA_TYPE)
