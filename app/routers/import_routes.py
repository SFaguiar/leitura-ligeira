import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import get_current_user
from app.database import get_connection
from app.extraction import extract_epub, extract_pdf, extract_url, validate_upload
from app.routers.documents import (
    MAX_TITLE_CHARS,
    _hash_text,
    _row_to_detail,
    _unique_title,
)
from app.schemas import DocumentDetail, UrlImportRequest

router = APIRouter()

MAX_FILE_BYTES = 50 * 1024 * 1024
# documents.py's MAX_TEXT_CHARS (500k) exists to catch an accidental paste —
# a real uploaded/imported book legitimately runs much longer (a long novel
# is a few million characters), so this path gets its own, higher ceiling.
# The 50MB file-size cap above is the real guard against abuse here.
MAX_IMPORT_TEXT_CHARS = 5_000_000


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _create_document(
    conn,
    user: dict,
    title: str,
    text: str,
    toc: list[dict] | None,
    format_: str,
    source_type: str,
    visibility: str,
) -> dict:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Não foi possível extrair texto do conteúdo enviado.")
    if len(text) > MAX_IMPORT_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Texto muito grande ({len(text):,} caracteres, máx. {MAX_IMPORT_TEXT_CHARS:,}).",
        )

    content_hash = _hash_text(text)
    # Same dedupe-by-owner rule as the paste endpoint in documents.py.
    existing = conn.execute(
        "SELECT * FROM documents WHERE content_hash = ? AND owner_id = ?",
        (content_hash, user["id"]),
    ).fetchone()
    if existing:
        return _row_to_detail(existing)

    title = _unique_title(conn, (title.strip() or "Untitled")[:MAX_TITLE_CHARS], user["id"])
    word_count = len(text.split())
    toc_json = json.dumps(toc) if toc else None

    cur = conn.execute(
        "INSERT INTO documents "
        "(title, format, source_type, raw_text, content_hash, word_count, owner_id, visibility, toc, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, format_, source_type, text, content_hash, word_count, user["id"], visibility, toc_json, _iso_now()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_detail(row)


@router.post("/documents/upload", response_model=DocumentDetail)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form("", max_length=MAX_TITLE_CHARS),
    visibility: str = Form("house", pattern="^(house|private)$"),
    user: dict = Depends(get_current_user),
):
    try:
        raw = await file.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo muito grande (máx. {MAX_FILE_BYTES // (1024 * 1024)}MB).",
            )

        original_name = file.filename or ""
        try:
            format_ = validate_upload(original_name, file.content_type, raw)
            if format_ == "pdf":
                text, toc = extract_pdf(raw)
            elif format_ == "epub":
                text, toc = extract_epub(raw)
            else:
                text, toc = raw.decode("utf-8", errors="replace"), None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        doc_title = title.strip() or original_name.rsplit(".", 1)[0]
        conn = get_connection()
        try:
            row = _create_document(
                conn,
                user,
                doc_title,
                text,
                toc,
                format_,
                "upload",
                visibility,
            )
        finally:
            conn.close()
        return row
    finally:
        await file.close()

@router.post("/documents/url", response_model=DocumentDetail)
def import_from_url(payload: UrlImportRequest, user: dict = Depends(get_current_user)):
    try:
        text, page_title = extract_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    visibility = "private" if payload.visibility == "private" else "house"
    doc_title = payload.title.strip() or page_title or payload.url

    conn = get_connection()
    try:
        row = _create_document(conn, user, doc_title, text, None, "txt", "url", visibility)
    finally:
        conn.close()
    return row
