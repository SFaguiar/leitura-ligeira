"""Validate the pinned native runtime and report optional local services."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
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
    version = ".".join(map(str, sys.version_info[:3]))
    print(f"Python: {version}")
    runtime_errors = check_runtime()
    print(f"Dependências: {'OK' if not runtime_errors else 'DIVERGENTES'}")
    for error in runtime_errors:
        print(f"  - {error}")
    print(f"Docker: {_command_version(['docker', '--version']) or 'não instalado'}")
    print(
        "Docker Compose: "
        f"{_command_version(['docker', 'compose', 'version']) or 'não instalado'}"
    )
    print(f"Kokoro: {'saudável' if kokoro_ready() else 'indisponível'}")
    print(f"Ollama: {_command_version(['ollama', '--version']) or 'não instalado'}")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.kokoro_ready:
        return 0 if kokoro_ready() else 1
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