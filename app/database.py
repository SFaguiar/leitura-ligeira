import logging
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "app.db"
SCHEMA_VERSION = 1
SQLITE_TIMEOUT_SECONDS = 5.0
_logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    format TEXT NOT NULL,
    source_type TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    lang TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    active_mode TEXT NOT NULL DEFAULT 'focus',
    wpm_focus INTEGER NOT NULL DEFAULT 300,
    wpm_flow INTEGER NOT NULL DEFAULT 250,
    chunk_focus INTEGER NOT NULL DEFAULT 1,
    chunk_flow INTEGER NOT NULL DEFAULT 1,
    font_focus INTEGER NOT NULL DEFAULT 48,
    font_flow INTEGER NOT NULL DEFAULT 20,
    orp_enabled INTEGER NOT NULL DEFAULT 0,
    nav_snap_back_on_click INTEGER NOT NULL DEFAULT 0,
    nav_pause_on_switch INTEGER NOT NULL DEFAULT 0,
    theme TEXT NOT NULL DEFAULT 'light',
    skin TEXT NOT NULL DEFAULT 'library',
    collect_stats INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS reading_progress (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'quero_ler',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (user_id, document_id)
);

CREATE TABLE IF NOT EXISTS reading_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    start_pointer INTEGER NOT NULL DEFAULT 0,
    end_pointer INTEGER,
    words_advanced INTEGER,
    avg_wpm REAL
);

-- Fase 8: generated TTS audio + word timings, cached per canonical block.
-- One row per (document, block-start, voice, model) — the UNIQUE key makes
-- POST /tts/blocks idempotent. audio_path is a filename under data/tts/;
-- timestamps_json is a list of {idx, start, end} keyed by GLOBAL token index.
CREATE TABLE IF NOT EXISTS tts_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    start_token INTEGER NOT NULL,
    end_token INTEGER NOT NULL,
    voice TEXT NOT NULL,
    model_version TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    timestamps_json TEXT NOT NULL,
    alignment_score REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (document_id, start_token, voice, model_version)
);
"""

# Columns added after the initial release — each gets a migration entry so
# existing databases pick them up without a manual reset.
MIGRATIONS = [
    ("content_hash", "ALTER TABLE documents ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''"),
    ("word_count", "ALTER TABLE documents ADD COLUMN word_count INTEGER NOT NULL DEFAULT 0"),
    ("lang", "ALTER TABLE documents ADD COLUMN lang TEXT"),
    (
        "owner_id",
        "ALTER TABLE documents ADD COLUMN owner_id INTEGER "
        "REFERENCES users(id) ON DELETE SET NULL",
    ),
    (
        "visibility",
        "ALTER TABLE documents ADD COLUMN visibility TEXT NOT NULL DEFAULT 'house' "
        "CHECK (visibility IN ('house', 'private'))",
    ),
    ("toc", "ALTER TABLE documents ADD COLUMN toc TEXT"),
    ("collection", "ALTER TABLE documents ADD COLUMN collection TEXT NOT NULL DEFAULT ''"),
]

USER_SETTINGS_MIGRATIONS = [
    ("skin", "ALTER TABLE user_settings ADD COLUMN skin TEXT NOT NULL DEFAULT 'library'"),
]

SCHEMA_OBJECTS = [
    (
        "idx_reading_progress_user",
        "CREATE INDEX IF NOT EXISTS idx_reading_progress_user ON reading_progress(user_id)",
    ),
    (
        "idx_reading_sessions_user_doc",
        "CREATE INDEX IF NOT EXISTS idx_reading_sessions_user_doc "
        "ON reading_sessions(user_id, document_id)",
    ),
    (
        "idx_reading_sessions_user_started",
        "CREATE INDEX IF NOT EXISTS idx_reading_sessions_user_started "
        "ON reading_sessions(user_id, started_at)",
    ),
    (
        "idx_documents_owner_created",
        "CREATE INDEX IF NOT EXISTS idx_documents_owner_created "
        "ON documents(owner_id, created_at DESC)",
    ),
    (
        "idx_documents_owner_hash",
        "CREATE INDEX IF NOT EXISTS idx_documents_owner_hash "
        "ON documents(owner_id, content_hash)",
    ),
    (
        "trg_documents_owner_insert",
        """
        CREATE TRIGGER IF NOT EXISTS trg_documents_owner_insert
        BEFORE INSERT ON documents
        FOR EACH ROW
        WHEN NEW.owner_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM users WHERE id = NEW.owner_id)
        BEGIN
            SELECT RAISE(ABORT, 'documents.owner_id inválido');
        END
        """,
    ),
    (
        "trg_documents_owner_update",
        """
        CREATE TRIGGER IF NOT EXISTS trg_documents_owner_update
        BEFORE UPDATE OF owner_id ON documents
        FOR EACH ROW
        WHEN NEW.owner_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM users WHERE id = NEW.owner_id)
        BEGIN
            SELECT RAISE(ABORT, 'documents.owner_id inválido');
        END
        """,
    ),
    (
        "trg_users_delete_document_owner",
        """
        CREATE TRIGGER IF NOT EXISTS trg_users_delete_document_owner
        AFTER DELETE ON users
        FOR EACH ROW
        BEGIN
            UPDATE documents SET owner_id = NULL WHERE owner_id = OLD.id;
        END
        """,
    ),
]

REQUIRED_TABLES = {
    "documents",
    "users",
    "user_settings",
    "reading_progress",
    "reading_sessions",
    "tts_blocks",
}
REQUIRED_OBJECTS = {name for name, _ in SCHEMA_OBJECTS}


class DatabaseIntegrityError(RuntimeError):
    pass


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    # busy_timeout and foreign_keys are per-connection pragmas — must be set
    # every time, unlike journal_mode which is persisted in the db file.
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _schema_object_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('index', 'trigger')"
        )
    }


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    if table not in _table_names(conn):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _assert_integrity(
    conn: sqlite3.Connection, *, check_foreign_keys: bool = True
) -> None:
    results = [str(row[0]) for row in conn.execute("PRAGMA integrity_check")]
    if results != ["ok"]:
        raise DatabaseIntegrityError(
            "PRAGMA integrity_check falhou: " + "; ".join(results)
        )
    if check_foreign_keys:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            summary = ", ".join(
                f"{row[0]} rowid={row[1]} -> {row[2]}" for row in violations[:10]
            )
            raise DatabaseIntegrityError(
                f"PRAGMA foreign_key_check encontrou {len(violations)} violação(ões): "
                f"{summary}"
            )
        orphan_owners = conn.execute(
            "SELECT COUNT(*) FROM documents d "
            "LEFT JOIN users u ON u.id = d.owner_id "
            "WHERE d.owner_id IS NOT NULL AND u.id IS NULL"
        ).fetchone()[0]
        if orphan_owners:
            raise DatabaseIntegrityError(
                f"documents.owner_id contém {orphan_owners} referência(s) órfã(s)."
            )


def _needs_migration(conn: sqlite3.Connection, had_schema: bool) -> bool:
    user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if user_version > SCHEMA_VERSION:
        raise DatabaseIntegrityError(
            f"Banco usa schema v{user_version}, superior ao suportado v{SCHEMA_VERSION}."
        )
    if not had_schema:
        return True
    if not REQUIRED_TABLES.issubset(_table_names(conn)):
        return True
    document_columns = _column_names(conn, "documents")
    if any(column not in document_columns for column, _ in MIGRATIONS):
        return True
    settings_columns = _column_names(conn, "user_settings")
    if any(column not in settings_columns for column, _ in USER_SETTINGS_MIGRATIONS):
        return True
    if not REQUIRED_OBJECTS.issubset(_schema_object_names(conn)):
        return True
    return user_version < SCHEMA_VERSION


def _migration_backup(db_path: Path, migration_backup_dir: Path | None) -> Path:
    from scripts.backup_restore import create_backup

    if migration_backup_dir is None:
        migration_backup_dir = (
            BASE_DIR / "backups" / "migrations"
            if db_path.resolve() == DB_PATH.resolve()
            else db_path.parent / "migration-backups"
        )
    return create_backup(
        database=db_path,
        secret_key=db_path.parent / "secret_key",
        output_dir=migration_backup_dir,
    )


def _repair_referential_integrity(conn: sqlite3.Connection) -> dict[str, int]:
    repairs = {}
    statements = [
        (
            "documents_owner",
            "UPDATE documents SET owner_id = NULL "
            "WHERE owner_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM users WHERE users.id = documents.owner_id)",
        ),
        (
            "user_settings",
            "DELETE FROM user_settings "
            "WHERE NOT EXISTS (SELECT 1 FROM users WHERE users.id = user_settings.user_id)",
        ),
        (
            "reading_progress",
            "DELETE FROM reading_progress "
            "WHERE NOT EXISTS (SELECT 1 FROM users WHERE users.id = reading_progress.user_id) "
            "OR NOT EXISTS (SELECT 1 FROM documents "
            "WHERE documents.id = reading_progress.document_id)",
        ),
        (
            "reading_sessions",
            "DELETE FROM reading_sessions "
            "WHERE NOT EXISTS (SELECT 1 FROM users WHERE users.id = reading_sessions.user_id) "
            "OR NOT EXISTS (SELECT 1 FROM documents "
            "WHERE documents.id = reading_sessions.document_id)",
        ),
        (
            "tts_blocks",
            "DELETE FROM tts_blocks "
            "WHERE NOT EXISTS (SELECT 1 FROM documents "
            "WHERE documents.id = tts_blocks.document_id)",
        ),
    ]
    for label, statement in statements:
        changed = conn.execute(statement).rowcount
        if changed:
            repairs[label] = changed
    return repairs


def _apply_schema(conn: sqlite3.Connection) -> dict[str, int]:
    conn.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
    try:
        columns = _column_names(conn, "documents")
        for column_name, migration_sql in MIGRATIONS:
            if column_name not in columns:
                conn.execute(migration_sql)
        settings_columns = _column_names(conn, "user_settings")
        for column_name, migration_sql in USER_SETTINGS_MIGRATIONS:
            if column_name not in settings_columns:
                conn.execute(migration_sql)

        # Backfill old space-separated timestamps ("YYYY-MM-DD HH:MM:SS") to
        # ISO 8601 with a Z suffix, so `new Date(...)` parses reliably on
        # every browser (space-separated is non-standard and Safari-hostile).
        conn.execute(
            "UPDATE documents SET created_at = replace(created_at, ' ', 'T') || 'Z' "
            "WHERE created_at NOT LIKE '%T%'"
        )
        # Backfill word_count for documents created before that column
        # existed. Safe to key off `= 0`: a real document can never have
        # zero words (raw_text is required non-empty at insert time).
        for row in conn.execute(
            "SELECT id, raw_text FROM documents WHERE word_count = 0"
        ):
            conn.execute(
                "UPDATE documents SET word_count = ? WHERE id = ?",
                (len(row["raw_text"].split()), row["id"]),
            )

        repairs = _repair_referential_integrity(conn)
        for _, statement in SCHEMA_OBJECTS:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        _assert_integrity(conn)
        conn.commit()
        return repairs
    except Exception:
        conn.rollback()
        raise


def check_database(db_path: Path = DB_PATH) -> dict[str, object]:
    conn = get_connection(db_path)
    try:
        _assert_integrity(conn)
        return {
            "integrity_check": "ok",
            "foreign_key_violations": 0,
            "schema_version": int(
                conn.execute("PRAGMA user_version").fetchone()[0]
            ),
            "journal_mode": str(
                conn.execute("PRAGMA journal_mode").fetchone()[0]
            ).lower(),
        }
    finally:
        conn.close()


def init_db(
    db_path: Path = DB_PATH,
    migration_backup_dir: Path | None = None,
) -> Path | None:
    db_path = Path(db_path).expanduser().resolve()
    conn = get_connection(db_path)
    try:
        tables = _table_names(conn)
        had_schema = bool(tables & REQUIRED_TABLES)
        if had_schema:
            _assert_integrity(conn, check_foreign_keys=False)
        needs_migration = _needs_migration(conn, had_schema)
    finally:
        conn.close()

    backup_path = None
    if had_schema and needs_migration:
        backup_path = _migration_backup(db_path, migration_backup_dir)
        _logger.warning("Backup pré-migração criado em %s", backup_path)

    if needs_migration:
        conn = get_connection(db_path)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            repairs = _apply_schema(conn)
            if repairs:
                _logger.warning(
                    "Referências órfãs reparadas após backup: %s",
                    ", ".join(f"{name}={count}" for name, count in repairs.items()),
                )
            _assert_integrity(conn)
        finally:
            conn.close()
    else:
        conn = get_connection(db_path)
        try:
            _assert_integrity(conn)
        finally:
            conn.close()
    return backup_path
