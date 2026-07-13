from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_connection
from app.routers.documents import _get_visible_document
from app.schemas import ProgressOut, ProgressUpdate

router = APIRouter()

VALID_STATUSES = {"quero_ler", "lendo", "lido", "abandonado"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/documents/{document_id}/progress", response_model=ProgressOut)
def get_progress(document_id: int, user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        doc = _get_visible_document(conn, document_id, user)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")

        conn.execute(
            "INSERT OR IGNORE INTO reading_progress (user_id, document_id) VALUES (?, ?)",
            (user["id"], document_id),
        )
        # Reabrir só promove 'quero_ler' -> 'lendo'; 'lido'/'abandonado' são
        # escolhas do usuário e não devem ser sobrescritas por só abrir.
        conn.execute(
            "UPDATE reading_progress SET status = 'lendo', updated_at = ? "
            "WHERE user_id = ? AND document_id = ? AND status = 'quero_ler'",
            (_iso_now(), user["id"], document_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM reading_progress WHERE user_id = ? AND document_id = ?",
            (user["id"], document_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


def save_progress(conn, user_id: int, document_id: int, position: int | None = None, status: str | None = None):
    """Shared upsert used by both this router and sessions.py's heartbeat —
    called as a plain function (not an HTTP round-trip) so a heartbeat PATCH
    can update position and session in one request. Caller commits."""
    conn.execute(
        "INSERT OR IGNORE INTO reading_progress (user_id, document_id) VALUES (?, ?)",
        (user_id, document_id),
    )
    updates = {}
    if position is not None:
        updates["position"] = position
    if status is not None:
        updates["status"] = status
    if updates:
        set_clause = ", ".join(f"{key} = ?" for key in updates)
        values = [*updates.values(), _iso_now(), user_id, document_id]
        conn.execute(
            f"UPDATE reading_progress SET {set_clause}, updated_at = ? "
            "WHERE user_id = ? AND document_id = ?",
            values,
        )
    return conn.execute(
        "SELECT * FROM reading_progress WHERE user_id = ? AND document_id = ?",
        (user_id, document_id),
    ).fetchone()


@router.put("/documents/{document_id}/progress", response_model=ProgressOut)
def update_progress(document_id: int, payload: ProgressUpdate, user: dict = Depends(get_current_user)):
    if payload.status is not None and payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status inválido: {payload.status}")

    conn = get_connection()
    try:
        doc = _get_visible_document(conn, document_id, user)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")

        row = save_progress(conn, user["id"], document_id, payload.position, payload.status)
        conn.commit()
    finally:
        conn.close()
    return dict(row)
