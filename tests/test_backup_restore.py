import sqlite3
import shutil
import unittest
import zipfile
from pathlib import Path
from uuid import uuid4

from scripts import backup_restore


BASE_DIR = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = BASE_DIR / "data" / "test-backup-restore"


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TEST_TEMP_ROOT / str(uuid4())
        self.root.mkdir()
        self.database = self.root / "source" / "app.db"
        self.database.parent.mkdir()
        conn = sqlite3.connect(self.database)
        try:
            conn.execute(
                "CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )
            conn.execute("INSERT INTO sample(value) VALUES ('documento preservado')")
            conn.commit()
        finally:
            conn.close()
        self.secret = self.database.parent / "secret_key"
        self.secret.write_text("segredo-de-teste", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        try:
            TEST_TEMP_ROOT.rmdir()
        except OSError:
            pass

    def _backup(self) -> Path:
        return backup_restore.create_backup(
            database=self.database,
            secret_key=self.secret,
            output_dir=self.root / "backups",
        )

    def test_backup_is_versioned_verified_and_restorable(self):
        backup = self._backup()
        self.assertIn("backup-v1-", backup.name)
        manifest = backup_restore.verify_backup(backup)
        self.assertEqual(manifest["format_version"], 1)

        target, rollback = backup_restore.restore_backup(
            backup, self.root / "clean-data"
        )
        self.assertIsNone(rollback)
        self.assertEqual(
            (target / "secret_key").read_text(encoding="utf-8"),
            "segredo-de-teste",
        )
        conn = sqlite3.connect(target / "app.db")
        try:
            value = conn.execute("SELECT value FROM sample").fetchone()[0]
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(value, "documento preservado")
        self.assertEqual(integrity, "ok")

    def test_restore_refuses_nonempty_target_without_replace(self):
        backup = self._backup()
        target = self.root / "existing-data"
        target.mkdir()
        (target / "keep.txt").write_text("não sobrescrever", encoding="utf-8")
        with self.assertRaisesRegex(backup_restore.BackupError, "não está vazio"):
            backup_restore.restore_backup(backup, target)
        self.assertEqual(
            (target / "keep.txt").read_text(encoding="utf-8"), "não sobrescrever"
        )

    def test_replace_preserves_previous_directory_as_rollback(self):
        backup = self._backup()
        target = self.root / "existing-data"
        target.mkdir()
        (target / "old.txt").write_text("estado anterior", encoding="utf-8")
        sqlite3.connect(target / "app.db").close()
        restored, rollback = backup_restore.restore_backup(backup, target, replace=True)
        self.assertEqual(restored, target)
        self.assertIsNotNone(rollback)
        self.assertEqual(
            (rollback / "old.txt").read_text(encoding="utf-8"), "estado anterior"
        )
        self.assertTrue((restored / "app.db").is_file())

    def test_replace_rejects_unrelated_nonempty_directory(self):
        backup = self._backup()
        target = self.root / "not-an-installation"
        target.mkdir()
        (target / "personal.txt").write_text("preservar", encoding="utf-8")
        with self.assertRaisesRegex(backup_restore.BackupError, "não contém um app.db"):
            backup_restore.restore_backup(backup, target, replace=True)
        self.assertTrue((target / "personal.txt").is_file())

    def test_modified_payload_fails_sha256_validation(self):
        backup = self._backup()
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(backup, "r") as source, zipfile.ZipFile(
            tampered, "w"
        ) as output:
            for info in source.infolist():
                content = source.read(info.filename)
                if info.filename == backup_restore.DATABASE_ARCHIVE_PATH:
                    content += b"alterado"
                output.writestr(info, content)
        with self.assertRaisesRegex(backup_restore.BackupError, "Integridade SHA-256"):
            backup_restore.verify_backup(tampered)

    def test_undeclared_archive_entry_is_rejected(self):
        backup = self._backup()
        unsafe = self.root / "unsafe.zip"
        with zipfile.ZipFile(backup, "r") as source, zipfile.ZipFile(
            unsafe, "w"
        ) as output:
            for info in source.infolist():
                output.writestr(info, source.read(info.filename))
            output.writestr("../escape.txt", "não extrair")
        with self.assertRaisesRegex(backup_restore.BackupError, "entradas extras"):
            backup_restore.verify_backup(unsafe)


if __name__ == "__main__":
    unittest.main()