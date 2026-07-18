import hashlib
import secrets

from fastapi import HTTPException, Request

from app.database import get_connection
from app.security import authenticated_user_for_request

# 200k rounds is a reasonable modern default — fast enough on a home PC,
# strong enough that a stolen DB file can't be brute-forced trivially.
PBKDF2_ITERATIONS = 200_000
# New credentials use a stronger cost while the historical value remains
# available solely to verify and transparently upgrade existing profiles.
CURRENT_PBKDF2_ITERATIONS = 600_000


def _password_digest(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    ).hex()


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Returns (hash_hex, salt_hex). Pass salt_hex to verify against an
    existing hash; omit it to generate a fresh salt for a new password."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = _password_digest(password, salt, CURRENT_PBKDF2_ITERATIONS)
    return digest, salt.hex()


def verify_password_details(
    password: str, salt_hex: str, expected_hash_hex: str
) -> tuple[bool, bool]:
    if not isinstance(salt_hex, str) or not isinstance(expected_hash_hex, str):
        return False, False
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        salt = b""
    if len(salt) != 16 or len(expected_hash_hex) != 64:
        return False, False
    current = _password_digest(password, salt, CURRENT_PBKDF2_ITERATIONS)
    legacy = _password_digest(password, salt, PBKDF2_ITERATIONS)
    current_match = secrets.compare_digest(current, expected_hash_hex)
    legacy_match = secrets.compare_digest(legacy, expected_hash_hex)
    return current_match or legacy_match, legacy_match and not current_match


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    valid, _needs_upgrade = verify_password_details(
        password, salt_hex, expected_hash_hex
    )
    return valid


def get_current_user(request: Request) -> dict:
    conn = get_connection()
    try:
        row = authenticated_user_for_request(conn, request)
    finally:
        conn.close()
    if row is None:
        # Session points at a user that no longer exists — clear it rather
        # than leave the client stuck retrying a dead session forever.
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    return dict(row)
