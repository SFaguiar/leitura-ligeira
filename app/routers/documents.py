import hashlib

from fastapi import APIRouter, HTTPException

from app.database import get_connection
from app.schemas import DocumentCreate, DocumentDetail, DocumentRename, DocumentSummary

router = APIRouter()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique_title(conn, base_title: str, exclude_id: int | None = None) -> str:
    query = "SELECT title FROM documents"
    params = ()
    if exclude_id is not None:
        query += " WHERE id != ?"
        params = (exclude_id,)
    existing = {row["title"] for row in conn.execute(query, params)}
    if base_title not in existing:
        return base_title
    n = 2
    while f"{base_title} ({n})" in existing:
        n += 1
    return f"{base_title} ({n})"


@router.post("/documents", response_model=DocumentDetail)
def create_document(payload: DocumentCreate):
    title = payload.title.strip() or "Untitled"
    text = payload.raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="raw_text must not be empty")
    content_hash = _hash_text(text)

    conn = get_connection()
    try:
        # Same content already in the library (e.g. accidental double-submit) — reuse it.
        existing = conn.execute(
            "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            return dict(existing)

        title = _unique_title(conn, title)
        cur = conn.execute(
            "INSERT INTO documents (title, format, source_type, raw_text, content_hash) VALUES (?, ?, ?, ?, ?)",
            (title, "txt", "paste", text, content_hash),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, title, format, source_type, created_at FROM documents ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)


@router.patch("/documents/{document_id}", response_model=DocumentDetail)
def rename_document(document_id: int, payload: DocumentRename):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title must not be empty")

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Document not found")

        title = _unique_title(conn, title, exclude_id=document_id)
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
def delete_document(document_id: int):
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
    finally:
        conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Document not found")
