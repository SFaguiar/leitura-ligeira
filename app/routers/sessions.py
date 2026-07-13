from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_connection
from app.routers.documents import _get_visible_document
from app.routers.progress import save_progress
from app.schemas import SessionCreate, SessionOut, SessionUpdate

router = APIRouter()

STALE_SESSION_MINUTES = 5


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _close_stale_sessions(conn, user_id: int, document_id: int):
    # No background task for a home-scale app — a session abandoned by an
    # app kill (no closeSession() call) just sits open until the same
    # user reopens the same document, at which point we close it here.
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STALE_SESSION_MINUTES)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    conn.execute(
        "UPDATE reading_sessions SET ended_at = updated_at "
        "WHERE user_id = ? AND document_id = ? AND ended_at IS NULL AND updated_at < ?",
        (user_id, document_id, cutoff),
    )


@router.post("/sessions", response_model=SessionOut)
def open_session(payload: SessionCreate, user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        doc = _get_visible_document(conn, payload.document_id, user)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")

        settings_row = conn.execute(
            "SELECT collect_stats FROM user_settings WHERE user_id = ?", (user["id"],)
        ).fetchone()
        if not settings_row or not settings_row["collect_stats"]:
            return {"session_id": None}

        _close_stale_sessions(conn, user["id"], payload.document_id)

        now = _iso_now()
        cur = conn.execute(
            "INSERT INTO reading_sessions "
            "(user_id, document_id, mode, started_at, updated_at, start_pointer) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user["id"], payload.document_id, payload.mode, now, now, payload.start_pointer),
        )
        conn.commit()
        session_id = cur.lastrowid
    finally:
        conn.close()
    return {"session_id": session_id}


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(session_id: int, payload: SessionUpdate, user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        session_row = conn.execute(
            "SELECT * FROM reading_sessions WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Session not found")

        now = _iso_now()
        words_advanced = payload.end_pointer - session_row["start_pointer"]
        if payload.ended_at:
            conn.execute(
                "UPDATE reading_sessions SET end_pointer = ?, words_advanced = ?, "
                "avg_wpm = ?, updated_at = ?, ended_at = ? WHERE id = ?",
                (payload.end_pointer, words_advanced, payload.avg_wpm, now, now, session_id),
            )
        else:
            conn.execute(
                "UPDATE reading_sessions SET end_pointer = ?, words_advanced = ?, "
                "avg_wpm = ?, updated_at = ? WHERE id = ?",
                (payload.end_pointer, words_advanced, payload.avg_wpm, now, session_id),
            )
        # Heartbeat unificado — salva a posição no mesmo request, sem round-trip extra.
        save_progress(conn, user["id"], session_row["document_id"], position=payload.position)
        conn.commit()
    finally:
        conn.close()
    return {"session_id": session_id}
