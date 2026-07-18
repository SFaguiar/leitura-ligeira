"""Bounded, privacy-safe diagnostics for required and optional local services."""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app import database, tts
from app.config import APP_VERSION, TransportSecurityConfig

_PROBE_TIMEOUT_SECONDS = 1.5
_MAX_PROBE_BODY_BYTES = 64 * 1024
_logger = logging.getLogger(__name__)


def _component(
    status: str,
    required: bool,
    message: str,
    *,
    version: str | None = None,
    latency_ms: int | None = None,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "required": required,
        "message": message,
    }
    if version:
        result["version"] = version
    if latency_ms is not None:
        result["latency_ms"] = latency_ms
    if details:
        result["details"] = details
    return result


def _safe_service_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL local inválida")
    if parsed.username or parsed.password:
        raise ValueError("credenciais embutidas não são permitidas")
    return f"{base_url.rstrip('/')}{path}"


def _probe_json_service(
    base_url: str,
    path: str,
    *,
    service_name: str,
    version_keys: tuple[str, ...] = (),
) -> dict[str, object]:
    started = time.monotonic()
    try:
        url = _safe_service_url(base_url, path)
        timeout = httpx.Timeout(_PROBE_TIMEOUT_SECONDS)
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return _component(
                        "unavailable",
                        False,
                        f"{service_name} respondeu HTTP {response.status_code}.",
                        latency_ms=round((time.monotonic() - started) * 1000),
                    )
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > _MAX_PROBE_BODY_BYTES:
                        raise ValueError("resposta excede o limite")
                    body.extend(chunk)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("resposta JSON inesperada")
        version = None
        for key in version_keys:
            value = payload.get(key)
            if isinstance(value, (str, int, float)) and value != "":
                version = str(value)
                break
        return _component(
            "healthy",
            False,
            f"{service_name} disponível.",
            version=version,
            latency_ms=round((time.monotonic() - started) * 1000),
        )
    except Exception as exc:
        _logger.info("Sonda opcional indisponível: %s", type(exc).__name__)
        return _component(
            "unavailable",
            False,
            f"{service_name} indisponível; os recursos principais continuam ativos.",
            latency_ms=round((time.monotonic() - started) * 1000),
        )


def database_health() -> dict[str, object]:
    started = time.monotonic()
    try:
        conn = database.get_connection()
        try:
            conn.execute("SELECT 1").fetchone()
            schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        finally:
            conn.close()
        return _component(
            "healthy",
            True,
            "Banco de dados disponível.",
            latency_ms=round((time.monotonic() - started) * 1000),
            details={"schema_version": schema_version},
        )
    except Exception:
        return _component(
            "unavailable",
            True,
            "Banco de dados indisponível.",
            latency_ms=round((time.monotonic() - started) * 1000),
        )


def database_diagnostics() -> dict[str, object]:
    started = time.monotonic()
    try:
        details = database.check_database()
        return _component(
            "healthy",
            True,
            "Integridade do banco de dados confirmada.",
            latency_ms=round((time.monotonic() - started) * 1000),
            details=details,
        )
    except Exception:
        return _component(
            "unavailable",
            True,
            "Não foi possível confirmar a integridade do banco de dados.",
            latency_ms=round((time.monotonic() - started) * 1000),
        )


def collect_diagnostics(
    transport: TransportSecurityConfig,
    request_scheme: str,
) -> dict[str, object]:
    """Collect required state and optional probes within a short fixed budget."""
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="ll-diagnostic") as pool:
        kokoro_future = pool.submit(
            _probe_json_service,
            tts.KOKORO_URL,
            "/health",
            service_name="Kokoro",
            version_keys=("version", "model"),
        )
        ollama_future = pool.submit(
            _probe_json_service,
            os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
            "/api/version",
            service_name="Ollama",
            version_keys=("version",),
        )
        kokoro = kokoro_future.result()
        ollama = ollama_future.result()

    database_component = database_diagnostics()
    request_is_https = request_scheme == "https"
    transport_status = "healthy" if request_is_https or not transport.lan_enabled else "degraded"
    transport_message = (
        "HTTPS ativo."
        if request_is_https
        else "HTTP local ativo; use LAN apenas em rede doméstica confiável."
    )
    components = {
        "application": _component(
            "healthy",
            True,
            "Aplicação disponível.",
            version=APP_VERSION,
        ),
        "database": database_component,
        "kokoro": kokoro,
        "ollama": ollama,
        "transport": _component(
            transport_status,
            True,
            transport_message,
            details={
                "https": request_is_https,
                "cookie_secure": transport.https_enabled,
                "lan_enabled": transport.lan_enabled,
            },
        ),
        "internet": _component(
            "not_required",
            False,
            "A internet não é necessária para biblioteca e leitura locais.",
        ),
    }
    required_failed = any(
        component["required"] and component["status"] == "unavailable"
        for component in components.values()
    )
    degraded = any(
        component["status"] in {"degraded", "unavailable"}
        for component in components.values()
    )
    return {
        "version": APP_VERSION,
        "status": "unhealthy" if required_failed else "degraded" if degraded else "healthy",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "components": components,
    }