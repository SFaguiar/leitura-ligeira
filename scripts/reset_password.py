#!/usr/bin/env python3
"""Admin-only CLI: reset a user's password directly in the database.

Not exposed via the HTTP API or the web UI on purpose — Fase 4 deliberately
left password reset out of scope (see ROADMAP.md). This is the documented
fallback: whoever has filesystem access to data/app.db runs this script.

Usage:
    python scripts/reset_password.py <nome-do-perfil>
"""
import getpass
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.database import get_connection


def main():
    if len(sys.argv) != 2:
        print("Uso: python scripts/reset_password.py <nome-do-perfil>")
        sys.exit(1)
    name = sys.argv[1].strip()

    conn = get_connection()
    try:
        row = conn.execute("SELECT id, role FROM users WHERE name = ?", (name,)).fetchone()
        if row is None:
            names = [r[0] for r in conn.execute("SELECT name FROM users ORDER BY name")]
            print(f"Perfil '{name}' não encontrado.")
            print(f"Perfis existentes: {', '.join(names) if names else '(nenhum)'}")
            sys.exit(1)
        user_id, role = row

        password = getpass.getpass(f"Nova senha para '{name}' ({role}): ")
        if not password:
            print("Senha vazia — cancelado.")
            sys.exit(1)
        confirm = getpass.getpass("Confirme a nova senha: ")
        if password != confirm:
            print("As senhas não coincidem — cancelado.")
            sys.exit(1)

        hash_hex, salt_hex = hash_password(password)
        conn.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            (hash_hex, salt_hex, user_id),
        )
        conn.commit()
    finally:
        conn.close()

    print(f"Senha de '{name}' redefinida com sucesso.")


if __name__ == "__main__":
    main()
