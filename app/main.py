"""Точка сборки FastAPI-приложения.

В образе Docker рядом лежит собранный фронт, и приложение отдаёт его само: один
адрес на всё, поэтому фронту не нужен отдельный origin, а значит и CORS. В dev
сборки нет — там фронт поднимает Vite на своём порту, и CORS как раз нужен.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import campaigns, configs, health, recipients, servers
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine
from app.schemas.envelope import ApiEnvelope
from app.services.config_worker import ConfigWorker
from app.services.mail_sender import MailSender
from app.services.worker import Worker

DEFAULT_CORS_ORIGIN = "http://localhost:5173"

# Куда собирается фронт. В образе каталог есть, в рабочей копии — только после
# `npm run build`, и тогда приложение начнёт отдавать его и в dev.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "admin-front" / "dist"


def _cors_origins(settings: Settings) -> list[str]:
    """Список origin из настройки через запятую; пустое значение — умолчание."""
    raw = settings.CORS_ORIGINS or DEFAULT_CORS_ORIGIN
    return [origin.strip() for origin in raw.split(",") if origin.strip()] or [DEFAULT_CORS_ORIGIN]


def _start_workers(app: FastAPI, settings: Settings) -> None:
    """Поднимает фоновые потоки отправки и генерации, кладёт их в state приложения."""
    app.state.worker = Worker(settings, MailSender(settings))
    app.state.worker.start()

    app.state.config_worker = ConfigWorker()
    app.state.config_worker.start()


def _stop_workers(app: FastAPI) -> None:
    app.state.worker.stop()
    app.state.config_worker.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # MVP: создаём таблицы, если их нет (позже заменит Alembic).
    Base.metadata.create_all(engine)

    _start_workers(app, get_settings())
    yield
    _stop_workers(app)


app = FastAPI(title="vibe_mail API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(get_settings()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiEnvelope(status="error", result=None, error=str(exc.detail)).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ApiEnvelope(status="error", result=None, error=str(exc.errors())).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ApiEnvelope(
            status="error", result=None, error="Внутренняя ошибка сервера"
        ).model_dump(),
    )


app.include_router(campaigns.router)
app.include_router(recipients.router)
app.include_router(configs.router)
app.include_router(servers.router)
app.include_router(health.router)


def _mount_frontend(application: FastAPI) -> None:
    """Отдаёт собранный фронт, если он рядом. Без сборки не делает ничего.

    Маршруты vue-router живут на клиенте (`createWebHistory`), поэтому на любой
    неизвестный путь отдаём index.html — иначе перезагрузка страницы на
    `/campaigns/1` вернула бы 404. Пути под /api из этого исключены: там 404 должен
    оставаться честным, а не превращаться в html.
    """
    if not (FRONTEND_DIR / "index.html").is_file():
        return

    application.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIR / "assets"),
        name="assets",
    )

    @application.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Не найдено")

        candidate = FRONTEND_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(FRONTEND_DIR / "index.html")


_mount_frontend(app)
