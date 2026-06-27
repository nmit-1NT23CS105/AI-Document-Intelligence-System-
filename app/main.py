from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router
from app.api.routes.summary import router as summary_router
from app.core.config import get_settings
from app.database.session import init_db

STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    fastapi_app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    fastapi_app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(documents_router)
    fastapi_app.include_router(search_router)
    fastapi_app.include_router(chat_router)
    fastapi_app.include_router(summary_router)
    fastapi_app.include_router(health_router)

    @fastapi_app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(INDEX_FILE)

    return fastapi_app


app = create_app()
