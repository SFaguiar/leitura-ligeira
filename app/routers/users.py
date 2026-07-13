from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import get_current_user, hash_password, verify_password
from app.database import get_connection
from app.schemas import (
    LoginRequest,
    UserCreate,
    UserMe,
    UserPublic,
    UserSettingsOut,
    UserSettingsUpdate,
)

router = APIRouter()


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
    if not payload.password:
        raise HTTPException(status_code=400, detail="Senha não pode ser vazia.")

    conn = get_connection()
    try:
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

        conn.commit()
        row = conn.execute("SELECT id, name, role FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()

    request.session["user_id"] = user_id
    return dict(row)


@router.post("/login", response_model=UserMe)
def login(payload: LoginRequest, request: Request):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE name = ?", (payload.name.strip(),)
        ).fetchone()
    finally:
        conn.close()
    if row is None or not verify_password(payload.password, row["password_salt"], row["password_hash"]):
        raise HTTPException(status_code=401, detail="Nome ou senha incorretos.")
    request.session["user_id"] = row["id"]
    return {"id": row["id"], "name": row["name"], "role": row["role"]}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
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
