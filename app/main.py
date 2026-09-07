"""Точка сборки FastAPI-приложения."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
