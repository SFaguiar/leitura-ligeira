"""Controles de segurança transversais da aplicação web.

Este módulo concentra sessão, CSRF, limitação de autenticação, validação de
Host e logging. Manter esses controles em um único ponto evita que um endpoint
novo seja publicado com uma variante mais fraca da mesma regra.
"""

import hashlib
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse


CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SESSION_TTL_DAYS = 30
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
_logger = logging.getLogger("leitura_ligeira.security")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_log_value(value: object, limit: int = 160) -> str:
    text = str(value).replace("\x00", "").strip()
    return "".join(char if char >= " " else "?" for char in text)[:limit]


def configure_security_logging(log_path: Path) -> None:
    """Configure one bounded, local JSON-lines security log."""
    resolved = Path(log_path).expanduser().resolve()
    if any(getattr(handler, "baseFilename", None) == str(resolved) for handler in _logger.handlers):
        return
    resolved.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        resolved,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    try:
        resolved.chmod(0o600)
    except OSError:
        # Windows ACLs do not always expose POSIX chmod semantics. The file
        # still lives under data/, outside StaticFiles and outside Git.
        pass


def client_ip(request: Request) -> str:
    return _clean_log_value(request.client.host if request.client else "unknown", 64)


def security_event(
    event: str,
    outcome: str,
    request: Request,
    *,
    subject: object | None = None,
    detail: object | None = None,
) -> None:
    payload = {
        "timestamp": _iso(_utc_now()),
        "event": _clean_log_value(event, 64),
        "outcome": _clean_log_value(outcome, 32),
        "client_ip": client_ip(request),
        "method": _clean_log_value(request.method, 12),
        "path": _clean_log_value(request.url.path, 256),
        "request_id": _clean_log_value(getattr(request.state, "request_id", ""), 32),
    }
    if subject is not None:
        payload["subject"] = _clean_log_value(subject)
    if detail is not None:
        payload["detail"] = _clean_log_value(detail)
    _logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def subject_fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().casefold().encode("utf-8")).hexdigest()[:16]


@dataclass
class _AttemptBucket:
    attempts: deque[float] = field(default_factory=deque)
    blocked_until: float = 0.0


class AuthenticationRateLimiter:
    """Bounded in-memory limiter for a single household application instance."""

    def __init__(
        self,
        *,
        account_limit: int = 5,
        ip_limit: int = 20,
        window_seconds: float = 5 * 60,
        block_seconds: float = 5 * 60,
        max_buckets: int = 2048,
        clock=time.monotonic,
    ):
        self.account_limit = account_limit
        self.ip_limit = ip_limit
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.max_buckets = max_buckets
        self._clock = clock
        self._buckets: dict[tuple[str, str], _AttemptBucket] = {}
        self._lock = threading.Lock()

    def _keys(self, ip: str, account: str) -> tuple[tuple[str, str], tuple[str, str]]:
        return ("ip", ip), ("account", subject_fingerprint(account))

    def _prune_bucket(self, bucket: _AttemptBucket, now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket.attempts and bucket.attempts[0] <= cutoff:
            bucket.attempts.popleft()
        if bucket.blocked_until <= now:
            bucket.blocked_until = 0.0

    def _trim(self, now: float) -> None:
        if len(self._buckets) <= self.max_buckets:
            return
        stale = []
        for key, bucket in self._buckets.items():
            self._prune_bucket(bucket, now)
            if not bucket.attempts and not bucket.blocked_until:
                stale.append(key)
        for key in stale:
            self._buckets.pop(key, None)
            if len(self._buckets) <= self.max_buckets:
                break
        while len(self._buckets) > self.max_buckets:
            self._buckets.pop(next(iter(self._buckets)))

    def retry_after(self, ip: str, account: str) -> int:
        now = self._clock()
        with self._lock:
            retry = 0.0
            for key in self._keys(ip, account):
                bucket = self._buckets.get(key)
                if bucket is None:
                    continue
                self._prune_bucket(bucket, now)
                retry = max(retry, bucket.blocked_until - now)
            return max(0, int(retry + 0.999))

    def failure(self, ip: str, account: str) -> None:
        now = self._clock()
        with self._lock:
            for key in self._keys(ip, account):
                bucket = self._buckets.setdefault(key, _AttemptBucket())
                self._prune_bucket(bucket, now)
                bucket.attempts.append(now)
                limit = self.ip_limit if key[0] == "ip" else self.account_limit
                if len(bucket.attempts) >= limit:
                    bucket.attempts.clear()
                    bucket.blocked_until = now + self.block_seconds
            self._trim(now)

    def success(self, ip: str, account: str) -> None:
        with self._lock:
            self._buckets.pop(self._keys(ip, account)[1], None)


LOGIN_RATE_LIMITER = AuthenticationRateLimiter()


def issue_csrf_token(request: Request, *, rotate: bool = False) -> str:
    token = request.session.get("csrf_token")
    if rotate or not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def enforce_csrf(request: Request) -> None:
    if request.method.upper() in SAFE_METHODS:
        return
    expected = request.session.get("csrf_token")
    supplied = request.headers.get(CSRF_HEADER)
    if (
        not isinstance(expected, str)
        or not isinstance(supplied, str)
        or not secrets.compare_digest(expected, supplied)
    ):
        security_event("csrf_validation", "denied", request)
        raise HTTPException(
            status_code=403,
            detail="Requisição de segurança inválida.",
            headers={"X-CSRF-Required": "1"},
        )


def _session_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


def start_authenticated_session(conn, request: Request, user_id: int) -> None:
    now = _utc_now()
    raw_token = secrets.token_urlsafe(32)
    previous_token = request.session.get("session_token")
    if isinstance(previous_token, str) and 32 <= len(previous_token) <= 128:
        conn.execute(
            "DELETE FROM auth_sessions WHERE token_hash = ?",
            (_session_hash(previous_token),),
        )
    conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (_iso(now),))
    conn.execute(
        "INSERT INTO auth_sessions "
        "(token_hash, user_id, created_at, expires_at, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            _session_hash(raw_token),
            user_id,
            _iso(now),
            _iso(now + timedelta(days=SESSION_TTL_DAYS)),
            _iso(now),
        ),
    )
    request.session.clear()
    request.session["session_token"] = raw_token
    issue_csrf_token(request, rotate=True)


def end_authenticated_session(conn, request: Request) -> None:
    raw_token = request.session.get("session_token")
    if isinstance(raw_token, str):
        conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_session_hash(raw_token),))
    request.session.clear()


def authenticated_user_for_request(conn, request: Request):
    raw_token = request.session.get("session_token")
    if not isinstance(raw_token, str) or not 32 <= len(raw_token) <= 128:
        return None
    return conn.execute(
        "SELECT u.id, u.name, u.role FROM auth_sessions s "
        "JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > ?",
        (_session_hash(raw_token), _iso(_utc_now())),
    ).fetchone()


def _configured_hosts() -> set[str]:
    hosts = {"localhost", "reader.local", socket.gethostname().casefold()}
    for raw in os.getenv("LEITURA_ALLOWED_HOSTS", "").split(","):
        host = raw.strip().rstrip(".").casefold()
        if host and _HOSTNAME_RE.fullmatch(host):
            hosts.add(host)
    return hosts


def request_host_is_allowed(host_header: str, *, lan_enabled: bool) -> bool:
    if not host_header or any(char in host_header for char in "\r\n\x00"):
        return False
    try:
        parsed = urlsplit(f"//{host_header}")
        hostname = (parsed.hostname or "").rstrip(".").casefold()
        if (
            parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or not hostname
        ):
            return False
        # Accessing parsed.port also validates malformed/non-numeric ports.
        _ = parsed.port
    except ValueError:
        return False
    normalized = hostname.strip("[]")
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return bool(_HOSTNAME_RE.fullmatch(hostname)) and hostname in _configured_hosts()
    if ip.is_loopback:
        return True
    return lan_enabled and (ip.is_private or ip.is_link_local)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware: Host validation, request IDs and hardening headers."""

    def __init__(self, app, *, lan_enabled: bool):
        self.app = app
        self.lan_enabled = lan_enabled

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request.state.request_id = secrets.token_hex(8)

        async def send_hardened(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                # Self-hosted single-instance app under active development — never let
                # the browser skip the network round-trip and serve a stale build.
                headers["Cache-Control"] = "no-store"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; base-uri 'none'; object-src 'none'; "
                    "frame-ancestors 'none'; form-action 'self'; "
                    "script-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'"
                )
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Cross-Origin-Resource-Policy"] = "same-origin"
                headers["X-Permitted-Cross-Domain-Policies"] = "none"
                headers["X-Robots-Tag"] = "noindex, nofollow"
                headers["X-Request-ID"] = request.state.request_id
                if scope.get("scheme") == "https":
                    headers["Strict-Transport-Security"] = "max-age=31536000"
                if message["status"] in {400, 401, 403, 413, 415, 422, 429}:
                    security_event(
                        "request_rejected",
                        "denied",
                        request,
                        detail=message["status"],
                    )
            await send(message)

        if not request_host_is_allowed(
            request.headers.get("host", ""), lan_enabled=self.lan_enabled
        ):
            security_event("host_validation", "denied", request)
            response = JSONResponse(
                status_code=400,
                content={"detail": "Host da requisição não permitido."},
            )
            await response(scope, receive, send_hardened)
            return

        await self.app(scope, receive, send_hardened)