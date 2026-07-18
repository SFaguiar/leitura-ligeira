import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import get_current_user, hash_password, verify_password_details
from app.database import get_connection
from app.security import (
    LOGIN_RATE_LIMITER,
    client_ip,
    end_authenticated_session,
    security_event,
    start_authenticated_session,
    subject_fingerprint,
)
from app.schemas import (
    LoginRequest,
    UserCreate,
    UserMe,
    UserPublic,
    UserSettingsOut,
    UserSettingsUpdate,
)

router = APIRouter()

_COMMON_PASSWORDS = frozenset(
    {
        "12345678",
        "123456789",
        "password",
        "qwerty123",
        "admin123",
        "letmein123",
        "leitura123",
    }
)
_DUMMY_SALT = "00" * 16
_DUMMY_HASH = "00" * 32


def _validate_new_password(password: str, name: str) -> None:
    normalized = password.casefold()
    if normalized in _COMMON_PASSWORDS or normalized == name.casefold():
        raise HTTPException(
            status_code=422,
            detail="Escolha uma senha menos previsível e diferente do nome do perfil.",
        )


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/users", response_model=list[UserPublic])
def list_users():
    # Public — this is what populates the Netflix-style profile picker
    # before anyone is logged in.
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name FROM users ORDER BY created_at").fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@router.post("/users", response_model=UserMe)
def create_user(payload: UserCreate, request: Request):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome não pode ser vazio.")
    if any(ord(char) < 32 for char in name):
        raise HTTPException(status_code=422, detail="Nome contém caracteres de controle.")
    if not payload.password:
        raise HTTPException(status_code=400, detail="Senha não pode ser vazia.")
    _validate_new_password(payload.password, name)

    conn = get_connection()
    try:
        # Serializa a eleição do primeiro administrador e impede que duas
        # criações concorrentes observem simultaneamente um banco sem usuários.
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Esse nome já está em uso.")

        is_first_user = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 0
        role = "admin" if is_first_user else "member"
        hash_hex, salt_hex = hash_password(payload.password)

        cur = conn.execute(
            "INSERT INTO users (name, password_hash, password_salt, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, hash_hex, salt_hex, role, _iso_now()),
        )
        user_id = cur.lastrowid
        conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))

        if is_first_user:
            # Documents created before accounts existed have no owner — hand
            # them to the first admin instead of leaving them ownerless and
            # unreachable now that every endpoint requires a logged-in user.
            conn.execute("UPDATE documents SET owner_id = ? WHERE owner_id IS NULL", (user_id,))

        start_authenticated_session(conn, request, user_id)
        conn.commit()
        row = conn.execute("SELECT id, name, role FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Esse nome já está em uso.") from exc
    finally:
        conn.close()

    security_event("profile_create", "success", request, subject=user_id)
    return dict(row)

@router.post("/login", response_model=UserMe)
def login(payload: LoginRequest, request: Request):
    name = payload.name.strip()
    ip = client_ip(request)
    subject = subject_fingerprint(name)
    retry_after = LOGIN_RATE_LIMITER.retry_after(ip, name)
    if retry_after:
        security_event("login", "rate_limited", request, subject=subject)
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde antes de tentar novamente.",
            headers={"Retry-After": str(retry_after)},
        )

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    finally:
        conn.close()

    salt = row["password_salt"] if row is not None else _DUMMY_SALT
    expected = row["password_hash"] if row is not None else _DUMMY_HASH
    valid, needs_upgrade = verify_password_details(payload.password, salt, expected)
    if row is None or not valid:
        LOGIN_RATE_LIMITER.failure(ip, name)
        security_event("login", "failure", request, subject=subject)
        raise HTTPException(status_code=401, detail="Nome ou senha incorretos.")

    LOGIN_RATE_LIMITER.success(ip, name)
    conn = get_connection()
    try:
        if needs_upgrade:
            upgraded_hash, _ = hash_password(payload.password, row["password_salt"])
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (upgraded_hash, row["id"]),
            )
        start_authenticated_session(conn, request, row["id"])
        conn.commit()
    finally:
        conn.close()
    security_event("login", "success", request, subject=row["id"])
    return {"id": row["id"], "name": row["name"], "role": row["role"]}


@router.post("/logout")
def logout(request: Request):
    conn = get_connection()
    try:
        end_authenticated_session(conn, request)
        conn.commit()
    finally:
        conn.close()
    security_event("logout", "success", request)
    return {"ok": True}

@router.get("/me", response_model=UserMe)
def read_me(user: dict = Depends(get_current_user)):
    return user


@router.get("/me/settings", response_model=UserSettingsOut)
def get_my_settings(user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user["id"],)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Settings not found")
    return dict(row)


@router.put("/me/settings", response_model=UserSettingsOut)
def update_my_settings(payload: UserSettingsUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    conn = get_connection()
    try:
        if updates:
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            values = [*updates.values(), _iso_now(), user["id"]]
            conn.execute(
                f"UPDATE user_settings SET {set_clause}, updated_at = ? WHERE user_id = ?",
                values,
            )
            conn.commit()
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user["id"],)
        ).fetchone()
    finally:
        conn.close()
    return dict(row)
