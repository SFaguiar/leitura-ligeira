import hashlib
import secrets

from fastapi import HTTPException, Request

from app.database import get_connection

# 200k rounds is a reasonable modern default — fast enough on a home PC,
# strong enough that a stolen DB file can't be brute-forced trivially.
PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Returns (hash_hex, salt_hex). Pass salt_hex to verify against an
    existing hash; omit it to generate a fresh salt for a new password."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    computed_hash_hex, _ = hash_password(password, salt_hex)
    return secrets.compare_digest(computed_hash_hex, expected_hash_hex)


def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, name, role FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        # Session points at a user that no longer exists — clear it rather
        # than leave the client stuck retrying a dead session forever.
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    return dict(row)
