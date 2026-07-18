import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import TransportSecurityConfig
from app.database import init_db
from app.routers import documents, import_routes, progress, sessions, stats, tts_routes, users

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
SECRET_KEY_PATH = BASE_DIR / "data" / "secret_key"


def _get_or_create_secret_key() -> str:
    SECRET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_KEY_PATH.exists():
        return SECRET_KEY_PATH.read_text().strip()
    key = secrets.token_hex(32)
    SECRET_KEY_PATH.write_text(key)
    return key


def create_app(transport: TransportSecurityConfig | None = None) -> FastAPI:
    transport = transport or TransportSecurityConfig.from_env()
    application = FastAPI(title="Leitura Ligeira")

    init_db()

    application.add_middleware(
        SessionMiddleware,
        secret_key=_get_or_create_secret_key(),
        max_age=60 * 60 * 24 * 30,  # 30 days — phones on the home network shouldn't have to log in constantly
        same_site="lax",
        https_only=transport.https_enabled,
    )

    application.include_router(users.router)
    application.include_router(documents.router)
    application.include_router(import_routes.router)
    application.include_router(progress.router)
    application.include_router(sessions.router)
    application.include_router(stats.router)
    application.include_router(tts_routes.router)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.middleware("http")
    async def no_cache(request: Request, call_next):
        # Self-hosted single-instance app under active development — never let
        # the browser skip the network round-trip and serve a stale build.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

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

    @application.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
