import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

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
    ("owner_id", "ALTER TABLE documents ADD COLUMN owner_id INTEGER"),
    ("visibility", "ALTER TABLE documents ADD COLUMN visibility TEXT NOT NULL DEFAULT 'house'"),
    ("toc", "ALTER TABLE documents ADD COLUMN toc TEXT"),
    ("collection", "ALTER TABLE documents ADD COLUMN collection TEXT NOT NULL DEFAULT ''"),
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # busy_timeout and foreign_keys are per-connection pragmas — must be set
    # every time, unlike journal_mode which is persisted in the db file.
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reading_progress_user ON reading_progress(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reading_sessions_user_doc ON reading_sessions(user_id, document_id)"
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reading_sessions_user_started ON reading_sessions(user_id, started_at)"
        )
        for column_name, migration_sql in MIGRATIONS:
            if column_name not in columns:
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
        for row in conn.execute("SELECT id, raw_text FROM documents WHERE word_count = 0"):
            conn.execute(
                "UPDATE documents SET word_count = ? WHERE id = ?",
                (len(row["raw_text"].split()), row["id"]),
            )
        conn.commit()
    finally:
        conn.close()
