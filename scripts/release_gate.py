"""Run the complete local release gate and persist a machine-readable report."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = BASE_DIR / "release-reports"


@dataclass(frozen=True)
class GateStep:
    name: str
    command: tuple[str, ...]
    timeout_seconds: float


def build_steps(*, include_docker: bool = True) -> list[GateStep]:
    python = sys.executable
    node = shutil.which("node") or "node"
    git = shutil.which("git") or "git"
    steps = [
        GateStep(
            "runtime-lock",
            (python, "scripts/check_environment.py", "--runtime"),
            30,
        ),
        GateStep(
            "python-tests",
            (python, "-m", "unittest", "discover", "-s", "tests", "-v"),
            180,
        ),
        GateStep(
            "python-compile",
            (python, "-m", "compileall", "-q", "app", "scripts", "tests"),
            60,
        ),
        GateStep("dependency-check", (python, "-m", "pip", "check"), 60),
        GateStep("js-rsvp-syntax", (node, "--check", "static/js/rsvp.js"), 30),
        GateStep("js-tts-syntax", (node, "--check", "static/js/tts.js"), 30),
        GateStep("js-app-syntax", (node, "--check", "static/js/app.js"), 30),
        GateStep("tts-regression", (node, "tests/tts_driver_test.mjs"), 60),
        GateStep("frontend-contract", (node, "tests/frontend_contract_test.mjs"), 60),
        GateStep("tts-4x-soak", (node, "tests/tts_soak_test.mjs"), 120),
        GateStep("git-whitespace", (git, "diff", "--check"), 30),
        GateStep("git-staged-whitespace", (git, "diff", "--cached", "--check"), 30),
    ]
    if include_docker:
        steps.append(GateStep("compose-contract", ("docker", "compose", "config", "-q"), 60))
    return steps


def run_step(step: GateStep) -> dict[str, object]:
    print(f"\n=== {step.name} ===", flush=True)
    started = time.monotonic()
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    try:
        result = subprocess.run(
            step.command,
            cwd=BASE_DIR,
            env=env,
            timeout=step.timeout_seconds,
            check=False,
        )
        status = "passed" if result.returncode == 0 else "failed"
        return_code = result.returncode
        error = None
    except subprocess.TimeoutExpired:
        status = "failed"
        return_code = None
        error = f"timeout após {step.timeout_seconds:g}s"
        print(f"[FALHOU] {error}", file=sys.stderr, flush=True)
    except OSError as exc:
        status = "failed"
        return_code = None
        error = f"não foi possível executar {step.command[0]} ({type(exc).__name__})"
        print(f"[FALHOU] {error}", file=sys.stderr, flush=True)
    duration = round(time.monotonic() - started, 3)
    if status == "passed":
        print(f"[OK] {step.name} ({duration:.3f}s)", flush=True)
    return {
        "name": step.name,
        "command": list(step.command),
        "timeout_seconds": step.timeout_seconds,
        "status": status,
        "return_code": return_code,
        "duration_seconds": duration,
        "error": error,
    }


def database_gate() -> dict[str, object]:
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    started = time.monotonic()
    try:
        from app.database import check_database

        details = check_database()
        status = "passed"
        error = None
    except Exception as exc:
        details = None
        status = "failed"
        error = f"verificação SQLite falhou ({type(exc).__name__})"
    duration = round(time.monotonic() - started, 3)
    print("\n=== database-integrity ===", flush=True)
    if status == "passed":
        print(
            "[OK] SQLite "
            f"schema={details['schema_version']} journal={details['journal_mode']} "
            f"({duration:.3f}s)",
            flush=True,
        )
    else:
        print(f"[FALHOU] {error}", file=sys.stderr, flush=True)
    return {
        "name": "database-integrity",
        "status": status,
        "duration_seconds": duration,
        "details": details,
        "error": error,
    }


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_report(report_dir: Path, report: dict[str, object]) -> Path:
    stamp = str(report["started_at"]).replace("-", "").replace(":", "")[:15]
    report_path = report_dir / f"release-gate-{stamp}.json"
    _write_json_atomic(report_path, report)
    _write_json_atomic(report_dir / "release-gate-latest.json", report)
    return report_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa o gate local da Release 1.0.")
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Pula somente a validação opcional do arquivo Compose.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Diretório dos relatórios JSON (padrão: release-reports).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started_at = datetime.now(UTC)
    steps = build_steps(include_docker=not args.skip_docker)
    results = [run_step(step) for step in steps]
    database_result = database_gate()
    success = all(item["status"] == "passed" for item in results)
    success = success and database_result["status"] == "passed"
    finished_at = datetime.now(UTC)
    report = {
        "gate_version": 1,
        "status": "passed" if success else "failed",
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "docker_check": "skipped" if args.skip_docker else "auto",
        "steps": results,
        "database": database_result,
    }
    report_path = write_report(args.report_dir.expanduser().resolve(), report)
    print(f"\nRelatório: {report_path}", flush=True)
    print(f"GATE DE RELEASE: {'APROVADO' if success else 'REPROVADO'}", flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())