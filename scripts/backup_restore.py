"""Backup and restore the persistent state required by Leitura Ligeira."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = BASE_DIR / "data" / "app.db"
DEFAULT_SECRET_KEY = BASE_DIR / "data" / "secret_key"
DEFAULT_BACKUP_DIR = BASE_DIR / "backups"
DEFAULT_RESTORE_DIR = BASE_DIR / "restored-data"
BACKUP_FORMAT = "leitura-ligeira-backup"
FORMAT_VERSION = 1
MANIFEST_PATH = "manifest.json"
DATABASE_ARCHIVE_PATH = "data/app.db"
SECRET_ARCHIVE_PATH = "data/secret_key"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ARCHIVE_FILES = 3
MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024


class BackupError(RuntimeError):
    """Raised when a backup cannot be created, verified, or restored safely."""


def _unique_directory(parent: Path, prefix: str) -> Path:
    for _ in range(100):
        candidate = parent / f"{prefix}{uuid4().hex}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise BackupError(f"Não foi possível reservar uma pasta temporária em {parent}.")


@contextmanager
def _working_directory(parent: Path, prefix: str):
    path = _unique_directory(parent, prefix)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_check(database: Path) -> str:
    try:
        conn = sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro", uri=True, timeout=5
        )
    except sqlite3.Error as exc:
        raise BackupError(f"Não foi possível abrir o banco restaurado: {exc}") from exc
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupError(f"Falha no PRAGMA integrity_check: {exc}") from exc
    finally:
        conn.close()
    status = str(result[0]) if result else ""
    if status.lower() != "ok":
        raise BackupError(f"PRAGMA integrity_check falhou: {status or 'sem resposta'}")
    return status


def _sqlite_snapshot(source: Path, destination: Path) -> int:
    if not source.is_file():
        raise BackupError(f"Banco de dados não encontrado: {source}")
    source_conn = None
    destination_conn = None
    try:
        source_conn = sqlite3.connect(
            f"file:{source.as_posix()}?mode=ro", uri=True, timeout=5
        )
        destination_conn = sqlite3.connect(destination, timeout=5)
        source_conn.execute("PRAGMA busy_timeout = 5000")
        source_conn.backup(destination_conn)
        destination_conn.commit()
        row = destination_conn.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error as exc:
        raise BackupError(f"Falha ao criar snapshot SQLite: {exc}") from exc
    finally:
        if destination_conn is not None:
            destination_conn.close()
        if source_conn is not None:
            source_conn.close()


def _file_record(path: Path, archive_path: str) -> dict[str, object]:
    return {
        "path": archive_path,
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _next_backup_path(output_dir: Path, timestamp: datetime) -> Path:
    stem = f"leitura-ligeira-backup-v{FORMAT_VERSION}-{timestamp:%Y%m%d-%H%M%S}"
    candidate = output_dir / f"{stem}.zip"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"{stem}-{suffix}.zip"
        suffix += 1
    return candidate


def create_backup(
    database: Path = DEFAULT_DATABASE,
    secret_key: Path = DEFAULT_SECRET_KEY,
    output_dir: Path = DEFAULT_BACKUP_DIR,
) -> Path:
    database = database.expanduser().resolve()
    secret_key = secret_key.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists() and not output_dir.is_dir():
        raise BackupError(f"O destino de backup não é uma pasta: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    created_at = _utc_now()
    final_path = _next_backup_path(output_dir, created_at)
    temp_archive = None
    try:
        with _working_directory(output_dir, ".ll-backup-") as temp_dir:
            snapshot = temp_dir / "app.db"
            user_version = _sqlite_snapshot(database, snapshot)
            _integrity_check(snapshot)

            files = [_file_record(snapshot, DATABASE_ARCHIVE_PATH)]
            include_secret = secret_key.is_file()
            if include_secret:
                files.append(_file_record(secret_key, SECRET_ARCHIVE_PATH))

            manifest = {
                "format": BACKUP_FORMAT,
                "format_version": FORMAT_VERSION,
                "created_at": created_at.isoformat(),
                "sqlite_user_version": user_version,
                "files": files,
                "excluded": ["data/tts", "certs"],
            }
            temp_archive = output_dir / f".leitura-ligeira-backup-{uuid4().hex}.zip"
            with zipfile.ZipFile(
                temp_archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as archive:
                archive.writestr(
                    MANIFEST_PATH,
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                )
                archive.write(snapshot, DATABASE_ARCHIVE_PATH)
                if include_secret:
                    archive.write(secret_key, SECRET_ARCHIVE_PATH)
            verify_backup(temp_archive)
            os.replace(temp_archive, final_path)
            temp_archive = None
        return final_path
    except (OSError, zipfile.BadZipFile) as exc:
        raise BackupError(f"Falha ao gravar o backup: {exc}") from exc
    finally:
        if temp_archive is not None:
            temp_archive.unlink(missing_ok=True)


def _validated_manifest(archive: zipfile.ZipFile) -> dict[str, object]:
    entries = archive.infolist()
    names = [entry.filename for entry in entries]
    if len(entries) > MAX_ARCHIVE_FILES or len(names) != len(set(names)):
        raise BackupError("O pacote contém entradas extras ou duplicadas.")
    if MANIFEST_PATH not in names:
        raise BackupError("Manifesto ausente no pacote de backup.")
    if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
        raise BackupError("O conteúdo descompactado excede o limite de segurança.")
    manifest_info = archive.getinfo(MANIFEST_PATH)
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        raise BackupError("Manifesto excede o limite de segurança.")
    try:
        manifest = json.loads(archive.read(MANIFEST_PATH).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("Manifesto inválido no pacote de backup.") from exc
    if manifest.get("format") != BACKUP_FORMAT:
        raise BackupError("O arquivo não é um backup do Leitura Ligeira.")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise BackupError(
            f"Versão de backup incompatível: {manifest.get('format_version')!r}."
        )
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise BackupError("Manifesto não contém a lista de arquivos.")
    allowed = {DATABASE_ARCHIVE_PATH, SECRET_ARCHIVE_PATH}
    recorded_names = set()
    for record in files:
        if not isinstance(record, dict):
            raise BackupError("Registro de arquivo inválido no manifesto.")
        name = record.get("path")
        if name not in allowed or name in recorded_names:
            raise BackupError("Caminho não permitido ou duplicado no manifesto.")
        if type(record.get("size")) is not int or record["size"] < 0:
            raise BackupError("Tamanho de arquivo inválido no manifesto.")
        digest = record.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise BackupError("Hash inválido no manifesto.")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise BackupError("Hash inválido no manifesto.") from exc
        recorded_names.add(name)
    if DATABASE_ARCHIVE_PATH not in recorded_names:
        raise BackupError("O banco de dados está ausente no manifesto.")
    if set(names) != recorded_names | {MANIFEST_PATH}:
        raise BackupError("O pacote contém arquivo não declarado no manifesto.")
    return manifest


def _extract_verified(backup_path: Path, destination: Path) -> dict[str, object]:
    try:
        with zipfile.ZipFile(backup_path, "r") as archive:
            manifest = _validated_manifest(archive)
            for record in manifest["files"]:
                name = record["path"]
                target = destination / Path(name).name
                digest = hashlib.sha256()
                size = 0
                with archive.open(name, "r") as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                if size != record["size"] or digest.hexdigest() != record["sha256"]:
                    raise BackupError(f"Integridade SHA-256 inválida para {name}.")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise BackupError(f"Pacote de backup inválido: {exc}") from exc
    _integrity_check(destination / "app.db")
    return manifest


def verify_backup(backup_path: Path) -> dict[str, object]:
    backup_path = backup_path.expanduser().resolve()
    if not backup_path.is_file():
        raise BackupError(f"Backup não encontrado: {backup_path}")
    with _working_directory(backup_path.parent, ".ll-verify-") as temp_dir:
        return _extract_verified(backup_path, temp_dir)


def _validate_restore_target(target: Path) -> Path:
    resolved = target.expanduser().resolve()
    if resolved == Path(resolved.anchor) or resolved == BASE_DIR:
        raise BackupError(f"Destino de restauração perigoso: {resolved}")
    if resolved.exists() and not resolved.is_dir():
        raise BackupError(f"O destino de restauração não é uma pasta: {resolved}")
    return resolved


def restore_backup(
    backup_path: Path,
    target_data_dir: Path = DEFAULT_RESTORE_DIR,
    replace: bool = False,
) -> tuple[Path, Path | None]:
    backup_path = backup_path.expanduser().resolve()
    if not backup_path.is_file():
        raise BackupError(f"Backup não encontrado: {backup_path}")
    target = _validate_restore_target(target_data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    has_content = target.exists() and any(target.iterdir())
    if has_content and not replace:
        raise BackupError(
            f"O destino não está vazio: {target}. Use --replace somente após conferir o caminho."
        )
    if has_content and replace and not (target / "app.db").is_file():
        raise BackupError(
            f"Substituição recusada: o destino não contém um app.db: {target}"
        )

    stage = _unique_directory(target.parent, ".ll-restore-")
    rollback = None
    moved_target = False
    try:
        _extract_verified(backup_path, stage)
        if target.exists():
            if has_content:
                timestamp = _utc_now().strftime("%Y%m%d-%H%M%S")
                rollback = target.with_name(f"{target.name}.pre-restore-{timestamp}")
                suffix = 1
                while rollback.exists():
                    rollback = target.with_name(
                        f"{target.name}.pre-restore-{timestamp}-{suffix}"
                    )
                    suffix += 1
                os.replace(target, rollback)
                moved_target = True
            else:
                target.rmdir()
        os.replace(stage, target)
        return target, rollback
    except OSError as exc:
        if moved_target and rollback is not None and not target.exists():
            os.replace(rollback, target)
        raise BackupError(
            f"Falha ao instalar a restauração; encerre o servidor e tente novamente: {exc}"
        ) from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cria, verifica e restaura backups íntegros do Leitura Ligeira."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser("backup", help="Cria um snapshot versionado.")
    backup.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    backup.add_argument("--secret-key", type=Path, default=DEFAULT_SECRET_KEY)
    backup.add_argument("--output-dir", type=Path, default=DEFAULT_BACKUP_DIR)

    verify = commands.add_parser("verify", help="Valida manifesto, hashes e SQLite.")
    verify.add_argument("backup", type=Path)

    restore = commands.add_parser("restore", help="Restaura primeiro em staging validado.")
    restore.add_argument("backup", type=Path)
    restore.add_argument("--target-data-dir", type=Path, default=DEFAULT_RESTORE_DIR)
    restore.add_argument(
        "--replace",
        action="store_true",
        help="Permite substituir destino não vazio, preservando uma pasta de rollback.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "backup":
            path = create_backup(args.database, args.secret_key, args.output_dir)
            print(f"Backup criado e verificado: {path}")
            print(
                "Guarde este arquivo como dado sensível: "
                "ele contém documentos e credenciais."
            )
        elif args.command == "verify":
            manifest = verify_backup(args.backup)
            print(
                f"Backup íntegro: formato v{manifest['format_version']}, "
                f"criado em {manifest['created_at']}."
            )
        else:
            target, rollback = restore_backup(
                args.backup, args.target_data_dir, args.replace
            )
            print(f"Restauração validada e instalada em: {target}")
            if rollback is not None:
                print(f"Estado anterior preservado em: {rollback}")
    except BackupError as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())