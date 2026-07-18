import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import database
from app.auth import get_current_user
from app.config import APP_VERSION, TransportSecurityConfig
from app.diagnostics import collect_diagnostics, database_health
from app.database import init_db
from app.routers import documents, import_routes, progress, sessions, stats, tts_routes, users
from app.schemas import HealthOut, SystemDiagnostics
from app.security import (
    SecurityHeadersMiddleware,
    configure_security_logging,
    enforce_csrf,
    issue_csrf_token,
    security_event,
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
SECRET_KEY_PATH = BASE_DIR / "data" / "secret_key"


def _get_or_create_secret_key() -> str:
    SECRET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_KEY_PATH.exists():
        key = SECRET_KEY_PATH.read_text(encoding="ascii").strip()
        if len(key) < 64:
            raise RuntimeError("data/secret_key está vazio ou inválido.")
        return key
    key = secrets.token_hex(32)
    try:
        descriptor = os.open(
            SECRET_KEY_PATH,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        return _get_or_create_secret_key()
    with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as output:
        output.write(key)
    return key


def create_app(transport: TransportSecurityConfig | None = None) -> FastAPI:
    transport = transport or TransportSecurityConfig.from_env()
    application = FastAPI(
        title="Leitura Ligeira",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(enforce_csrf)],
    )

    init_db()
    configure_security_logging(database.DB_PATH.parent / "logs" / "security.log")

    application.add_middleware(
        SessionMiddleware,
        secret_key=_get_or_create_secret_key(),
        session_cookie="ll_session",
        max_age=60 * 60 * 24 * 30,  # 30 days — phones on the home network shouldn't have to log in constantly
        same_site="lax",
        https_only=transport.https_enabled,
    )
    application.add_middleware(
        SecurityHeadersMiddleware,
        lan_enabled=transport.lan_enabled,
    )
    application.include_router(users.router)
    application.include_router(documents.router)
    application.include_router(import_routes.router)
    application.include_router(progress.router)
    application.include_router(sessions.router)
    application.include_router(stats.router)
    application.include_router(tts_routes.router)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        security_event(
            "unhandled_exception",
            "failure",
            request,
            detail=type(exc).__name__,
        )
        request_id = getattr(request.state, "request_id", secrets.token_hex(8))
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Erro interno inesperado.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    @application.get("/security/csrf")
    def csrf_token(request: Request):
        return {"token": issue_csrf_token(request)}
    @application.get("/system/transport")
    def transport_status(request: Request):
        request_is_https = request.url.scheme == "https"
        return {
            "scheme": request.url.scheme,
            "https": request_is_https,
            "cookie_secure": transport.https_enabled,
            "lan_enabled": transport.lan_enabled,
            "warning": None if request_is_https else "HTTP sem criptografia; use somente em rede doméstica confiável.",
        }

    @application.get("/system/health", response_model=HealthOut)
    def health_status():
        database_component = database_health()
        healthy = database_component["status"] == "healthy"
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "version": APP_VERSION,
                "status": "healthy" if healthy else "unhealthy",
                "database": database_component["status"],
            },
        )

    @application.get("/system/diagnostics", response_model=SystemDiagnostics)
    def system_diagnostics(
        request: Request,
        user: dict = Depends(get_current_user),
    ):
        return collect_diagnostics(transport, request.url.scheme)

    @application.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
