import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.routers import documents, progress, sessions, users

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


app = FastAPI(title="Leitura Ligeira")

init_db()

app.add_middleware(
    SessionMiddleware,
    secret_key=_get_or_create_secret_key(),
    max_age=60 * 60 * 24 * 30,  # 30 days — phones on the home network shouldn't have to log in constantly
    same_site="lax",
)

app.include_router(users.router)
app.include_router(documents.router)
app.include_router(progress.router)
app.include_router(sessions.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_cache(request: Request, call_next):
    # Self-hosted single-instance app under active development — never let
    # the browser skip the network round-trip and serve a stale build.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
