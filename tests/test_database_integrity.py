import ast
import shutil
import sqlite3
import unittest
from unittest import mock
import zipfile
from pathlib import Path
from uuid import uuid4

from app import database
from scripts import backup_restore


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_ROOT = BASE_DIR / "data" / "test-database-integrity"


def _legacy_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                format TEXT NOT NULL,
                source_type TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT '2026-01-01 12:00:00'
            );
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL DEFAULT '2026-01-01T12:00:00Z'
            );
            CREATE TABLE user_settings (
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
                updated_at TEXT NOT NULL DEFAULT '2026-01-01T12:00:00Z'
            );
            CREATE TABLE reading_progress (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                position INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'quero_ler',
                updated_at TEXT NOT NULL DEFAULT '2026-01-01T12:00:00Z',
                PRIMARY KEY (user_id, document_id)
            );
            CREATE TABLE reading_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                mode TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                updated_at TEXT NOT NULL,
                start_pointer INTEGER NOT NULL DEFAULT 0,
                end_pointer INTEGER,
                words_advanced INTEGER,
                avg_wpm REAL
            );
            INSERT INTO users(id, name, password_hash, password_salt)
            VALUES (1, 'Legado', 'hash', 'salt');
            INSERT INTO user_settings(user_id) VALUES (1);
            INSERT INTO documents(id, title, format, source_type, raw_text)
            VALUES (1, 'Documento legado', 'txt', 'paste', 'duas palavras');
            INSERT INTO reading_progress(user_id, document_id) VALUES (1, 1);
            INSERT INTO reading_progress(user_id, document_id) VALUES (1, 999);
            INSERT INTO reading_sessions(
                user_id, document_id, mode, started_at, updated_at, start_pointer
            ) VALUES (1, 999, 'focus', '2026-01-01T12:00:00Z',
                      '2026-01-01T12:00:00Z', 0);
            """
        )
        conn.commit()
    finally:
        conn.close()


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TEST_ROOT / str(uuid4())
        self.root.mkdir()
        self.db_path = self.root / "data" / "app.db"
        self.db_path.parent.mkdir()
        self.backup_dir = self.root / "backups"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        try:
            TEST_ROOT.rmdir()
        except OSError:
            pass

    def test_empty_database_initializes_without_backup_and_is_idempotent(self):
        first_backup = database.init_db(self.db_path, self.backup_dir)
        self.assertIsNone(first_backup)
        state = database.check_database(self.db_path)
        self.assertEqual(state["integrity_check"], "ok")
        self.assertEqual(state["foreign_key_violations"], 0)
        self.assertEqual(state["schema_version"], database.SCHEMA_VERSION)
        self.assertEqual(state["journal_mode"], "wal")
        self.assertEqual(list(self.backup_dir.glob("*.zip")), [])

        second_backup = database.init_db(self.db_path, self.backup_dir)
        self.assertIsNone(second_backup)
        self.assertEqual(list(self.backup_dir.glob("*.zip")), [])

    def test_legacy_database_is_backed_up_migrated_and_repaired(self):
        _legacy_database(self.db_path)
        backup = database.init_db(self.db_path, self.backup_dir)
        self.assertIsNotNone(backup)
        self.assertTrue(backup.is_file())
        self.assertEqual(database.check_database(self.db_path)["schema_version"], 1)

        conn = database.get_connection(self.db_path)
        try:
            document_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(documents)")
            }
            settings_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(user_settings)")
            }
            self.assertIn("collection", document_columns)
            self.assertIn("skin", settings_columns)
            self.assertEqual(
                conn.execute("SELECT word_count FROM documents WHERE id = 1").fetchone()[0],
                2,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM reading_progress").fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM reading_sessions").fetchone()[0],
                0,
            )
            objects = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('index', 'trigger')"
                )
            }
            self.assertTrue(database.REQUIRED_OBJECTS.issubset(objects))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO documents("
                    "title, format, source_type, raw_text, owner_id"
                    ") VALUES ('inválido', 'txt', 'paste', 'texto', 999)"
                )
        finally:
            conn.close()

        restored, _ = backup_restore.restore_backup(
            backup, self.root / "pre-migration"
        )
        legacy = sqlite3.connect(restored / "app.db")
        try:
            old_columns = {
                row[1] for row in legacy.execute("PRAGMA table_info(documents)")
            }
            self.assertNotIn("collection", old_columns)
            self.assertEqual(
                legacy.execute(
                    "SELECT COUNT(*) FROM reading_progress WHERE document_id = 999"
                ).fetchone()[0],
                1,
            )
        finally:
            legacy.close()

        backup_count = len(list(self.backup_dir.glob("*.zip")))
        self.assertIsNone(database.init_db(self.db_path, self.backup_dir))
        self.assertEqual(len(list(self.backup_dir.glob("*.zip"))), backup_count)

    def test_failed_migration_rolls_back_every_schema_change(self):
        _legacy_database(self.db_path)
        with mock.patch.object(
            database,
            "_repair_referential_integrity",
            side_effect=RuntimeError("falha forçada"),
        ):
            with self.assertRaisesRegex(RuntimeError, "falha forçada"):
                database.init_db(self.db_path, self.backup_dir)

        self.assertEqual(len(list(self.backup_dir.glob("*.zip"))), 1)
        legacy = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1] for row in legacy.execute("PRAGMA table_info(documents)")
            }
            self.assertNotIn("collection", columns)
            self.assertEqual(
                legacy.execute(
                    "SELECT COUNT(*) FROM reading_progress WHERE document_id = 999"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(legacy.execute("PRAGMA user_version").fetchone()[0], 0)
        finally:
            legacy.close()

    def test_newer_schema_is_rejected_without_backup(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(f"PRAGMA user_version = {database.SCHEMA_VERSION + 1}")
            conn.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY)")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(database.DatabaseIntegrityError, "superior"):
            database.init_db(self.db_path, self.backup_dir)
        self.assertFalse(self.backup_dir.exists())


class ConnectionLifecycleTests(unittest.TestCase):
    def test_every_get_connection_assignment_has_try_finally_close(self):
        checked = 0
        paths = list((BASE_DIR / "app").rglob("*.py"))
        paths.append(BASE_DIR / "scripts" / "reset_password.py")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                for field in ("body", "orelse"):
                    body = getattr(node, field, None)
                    if not isinstance(body, list):
                        continue
                    for index, statement in enumerate(body[:-1]):
                        if not isinstance(statement, ast.Assign):
                            continue
                        if not isinstance(statement.value, ast.Call):
                            continue
                        function = statement.value.func
                        if not isinstance(function, ast.Name) or function.id != "get_connection":
                            continue
                        self.assertEqual(len(statement.targets), 1, path)
                        target = statement.targets[0]
                        self.assertIsInstance(target, ast.Name, path)
                        following = body[index + 1]
                        self.assertIsInstance(following, ast.Try, path)
                        closed = any(
                            isinstance(item, ast.Call)
                            and isinstance(item.func, ast.Attribute)
                            and isinstance(item.func.value, ast.Name)
                            and item.func.value.id == target.id
                            and item.func.attr == "close"
                            for final_statement in following.finalbody
                            for item in ast.walk(final_statement)
                        )
                        self.assertTrue(
                            closed,
                            f"{path}: {target.id} não fecha no finally imediato",
                        )
                        checked += 1
        self.assertGreaterEqual(checked, 20)


if __name__ == "__main__":
    unittest.main()