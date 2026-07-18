"""Validate the pinned native runtime and report optional local services."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
LOCK_PATH = BASE_DIR / "requirements.lock"
MIN_PYTHON = (3, 13, 11)
MAX_PYTHON = (3, 14, 0)
PIN_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)$")


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path = LOCK_PATH) -> dict[str, tuple[str, str]]:
    if not path.is_file():
        raise RuntimeError(f"Lock de dependências não encontrado: {path}")
    pins = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_PATTERN.fullmatch(line)
        if match is None:
            raise RuntimeError(
                f"Linha {line_number} de requirements.lock não é um pin exato: {line!r}"
            )
        display_name, version = match.groups()
        normalized = _normalize_name(display_name)
        if normalized in pins:
            raise RuntimeError(f"Dependência duplicada no lock: {display_name}")
        pins[normalized] = (display_name, version)
    if not pins:
        raise RuntimeError("requirements.lock está vazio.")
    return pins


def python_version_error(version: tuple[int, int, int]) -> str | None:
    if version < MIN_PYTHON or version >= MAX_PYTHON:
        return (
            "Python incompatível: "
            f"{version[0]}.{version[1]}.{version[2]}; "
            "use Python >=3.13.11 e <3.14."
        )
    return None


def dependency_errors(
    pins: dict[str, tuple[str, str]],
    installed: dict[str, str] | None = None,
) -> list[str]:
    if installed is None:
        installed = {
            _normalize_name(dist.metadata["Name"]): dist.version
            for dist in importlib.metadata.distributions()
            if dist.metadata.get("Name")
        }
    errors = []
    for normalized, (display_name, expected) in pins.items():
        actual = installed.get(normalized)
        if actual is None:
            errors.append(f"{display_name}: ausente (esperado {expected})")
        elif actual != expected:
            errors.append(f"{display_name}: instalado {actual}, esperado {expected}")
    return errors


def check_runtime() -> list[str]:
    errors = []
    version = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    version_error = python_version_error(version)
    if version_error:
        errors.append(version_error)
    try:
        pins = read_lock()
    except RuntimeError as exc:
        errors.append(str(exc))
    else:
        errors.extend(dependency_errors(pins))
    return errors


def kokoro_ready(timeout: float = 1.0) -> bool:
    request = urllib.request.Request(
        "http://127.0.0.1:8880/health",
        headers={"User-Agent": "Leitura-Ligeira-Environment-Check/1.0"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read(64 * 1024).decode("utf-8"))
            return isinstance(payload, dict)
    except (OSError, ValueError, urllib.error.URLError):
        return False


def wait_for_kokoro(timeout: float, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if kokoro_ready(timeout=min(1.0, max(0.2, interval))):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(interval, remaining))


def docker_ready(timeout: float = 5.0) -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{json .ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _json_endpoint(url: str, timeout: float = 1.0) -> dict | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Leitura-Ligeira-Environment-Check/1.0"},
    )
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context),
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read(64 * 1024).decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def ollama_status(timeout: float = 1.0) -> str:
    base = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "configuração inválida (opcional)"
    if parsed.username or parsed.password:
        return "configuração inválida (opcional)"
    payload = _json_endpoint(f"{base}/api/version", timeout)
    if payload is None:
        return "indisponível (opcional)"
    version = payload.get("version")
    return f"saudável ({version})" if version else "saudável"


def application_status(timeout: float = 1.0) -> str:
    try:
        port = int(os.environ.get("LEITURA_PORT", "8000"))
    except ValueError:
        return "configuração de porta inválida"
    if not 1 <= port <= 65535:
        return "configuração de porta inválida"
    for scheme in ("https", "http"):
        payload = _json_endpoint(f"{scheme}://127.0.0.1:{port}/system/health", timeout)
        if payload is not None:
            return f"{payload.get('status', 'respondeu')} em {scheme.upper()}"
    return "não iniciada"


def _command_version(command: list[str], timeout: float = 4.0) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "instalado, mas não respondeu"
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[-1] if output else f"código {result.returncode}"


def print_diagnostics() -> int:
    from app.config import APP_VERSION, TransportSecurityConfig
    from app.database import check_database

    version = ".".join(map(str, sys.version_info[:3]))
    print(f"Leitura Ligeira: {APP_VERSION}")
    print(f"Python: {version}")
    runtime_errors = check_runtime()
    print(f"Dependências: {'OK' if not runtime_errors else 'DIVERGENTES'}")
    for error in runtime_errors:
        print(f"  - {error}")
    try:
        database = check_database()
        print(
            "SQLite: saudável "
            f"(schema {database['schema_version']}, {database['journal_mode']})"
        )
    except Exception:
        print("SQLite: indisponível")
    print(f"Aplicação: {application_status()}")
    print(f"Docker CLI: {_command_version(['docker', '--version']) or 'não instalado'}")
    print(f"Docker Engine: {'ativo' if docker_ready() else 'indisponível (opcional)'}")
    print(
        "Docker Compose: "
        f"{_command_version(['docker', 'compose', 'version']) or 'não instalado'}"
    )
    print(f"Kokoro: {'saudável' if kokoro_ready() else 'indisponível (opcional)'}")
    print(f"Ollama: {ollama_status()}")
    try:
        transport = TransportSecurityConfig.from_env()
        https_status = "configurado" if transport.https_enabled else "opcional/desativado"
    except RuntimeError:
        https_status = "configuração inválida"
    print(f"HTTPS: {https_status}")
    print("Internet: não requerida para biblioteca e leitura locais")
    return 0 if not runtime_errors else 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verifica o ambiente do Leitura Ligeira.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--runtime", action="store_true", help="Valida Python e requirements.lock."
    )
    mode.add_argument(
        "--kokoro-ready",
        action="store_true",
        help="Retorna zero se o Kokoro estiver saudável.",
    )
    mode.add_argument(
        "--diagnose", action="store_true", help="Exibe versões e serviços opcionais."
    )
    mode.add_argument(
        "--docker-ready",
        action="store_true",
        help="Retorna zero se o Docker Engine responder.",
    )
    mode.add_argument(
        "--wait-kokoro",
        type=float,
        metavar="SEGUNDOS",
        help="Aguarda o Kokoro por um prazo máximo.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.kokoro_ready:
        return 0 if kokoro_ready() else 1
    if args.docker_ready:
        return 0 if docker_ready() else 1
    if args.wait_kokoro is not None:
        return 0 if wait_for_kokoro(args.wait_kokoro) else 1
    if args.diagnose:
        return print_diagnostics()
    errors = check_runtime()
    if not errors:
        print("Ambiente Python reproduzível: OK")
        return 0
    print("[ERRO] O ambiente virtual diverge de requirements.lock:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    print(
        "Recrie o ambiente ou execute: "
        ".venv\\Scripts\\python.exe -m pip install -r requirements.lock",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())