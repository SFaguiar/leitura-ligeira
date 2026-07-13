import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_connection
from app.schemas import DocumentCreate, DocumentDetail, DocumentRename, DocumentSummary

router = APIRouter()

# A pasted/uploaded blob beyond this is almost certainly a mistake (or, once
# Fase 6 lands, a scanned-PDF-sized outlier) — reject with a clear message
# instead of silently loading a multi-megabyte string into the browser.
MAX_TEXT_CHARS = 500_000
MAX_TITLE_CHARS = 200


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unique_title(conn, base_title: str, owner_id: int, exclude_id: int | None = None) -> str:
    # Scoped per owner — two people are each allowed a document called
    # "Capítulo 1" without one getting stuck with an ugly suffix because of
    # the other's library.
    query = "SELECT title FROM documents WHERE owner_id = ?"
    params: list = [owner_id]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)
    existing = {row["title"] for row in conn.execute(query, params)}
    if base_title not in existing:
        return base_title
    n = 2
    while f"{base_title} ({n})" in existing:
        n += 1
    return f"{base_title} ({n})"


def _get_visible_document(conn, document_id: int, user: dict):
    """Returns the row, or None if it doesn't exist or is someone else's
    private document (treated identically — a 404 shouldn't confirm that a
    private document exists)."""
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        return None
    if row["visibility"] == "private" and row["owner_id"] != user["id"]:
        return None
    return row


def _can_manage(doc_row, user: dict) -> bool:
    if doc_row["owner_id"] == user["id"]:
        return True
    if user["role"] == "admin" and doc_row["visibility"] == "house":
        return True
    return False


@router.post("/documents", response_model=DocumentDetail)
def create_document(payload: DocumentCreate, user: dict = Depends(get_current_user)):
    title = payload.title.strip() or "Untitled"
    text = payload.raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="raw_text must not be empty")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Texto muito grande ({len(text):,} caracteres, máx. {MAX_TEXT_CHARS:,}).",
        )
    title = title[:MAX_TITLE_CHARS]
    visibility = "private" if payload.visibility == "private" else "house"
    content_hash = _hash_text(text)
    word_count = len(text.split())

    conn = get_connection()
    try:
        # Same content already in *this user's* library (e.g. accidental
        # double-submit) — reuse it. Scoped to the owner: matching against
        # everyone's hashes would let pasting the same text as someone
        # else's private document hand you back their private content.
        existing = conn.execute(
            "SELECT * FROM documents WHERE content_hash = ? AND owner_id = ?",
            (content_hash, user["id"]),
        ).fetchone()
        if existing:
            return dict(existing)

        title = _unique_title(conn, title, user["id"])
        cur = conn.execute(
            "INSERT INTO documents "
            "(title, format, source_type, raw_text, content_hash, word_count, owner_id, visibility, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, "txt", "paste", text, content_hash, word_count, user["id"], visibility, _iso_now()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, title, format, source_type, word_count, visibility, owner_id, created_at "
            "FROM documents WHERE visibility = 'house' OR owner_id = ? "
            "ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        row = _get_visible_document(conn, document_id, user)
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)


@router.patch("/documents/{document_id}", response_model=DocumentDetail)
def rename_document(document_id: int, payload: DocumentRename, user: dict = Depends(get_current_user)):
    title = payload.title.strip()[:MAX_TITLE_CHARS]
    if not title:
        raise HTTPException(status_code=400, detail="title must not be empty")

    conn = get_connection()
    try:
        existing = _get_visible_document(conn, document_id, user)
        if existing is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if not _can_manage(existing, user):
            raise HTTPException(status_code=403, detail="Você não tem permissão para editar este documento.")

        title = _unique_title(conn, title, existing["owner_id"], exclude_id=document_id)
        conn.execute(
            "UPDATE documents SET title = ? WHERE id = ?", (title, document_id)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        existing = _get_visible_document(conn, document_id, user)
        if existing is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if not _can_manage(existing, user):
            raise HTTPException(status_code=403, detail="Você não tem permissão para excluir este documento.")

        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
    finally:
        conn.close()
