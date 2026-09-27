"""Зависимости FastAPI: сессия БД и доступ к фоновым воркерам."""

from fastapi import Request

from app.db.session import get_db
from app.services.config_worker import ConfigWorker
from app.services.worker import Worker

__all__ = ["get_config_worker", "get_db", "get_worker"]


def get_worker(request: Request) -> Worker:
    """Возвращает запущенный воркер из состояния приложения."""
    return request.app.state.worker


def get_config_worker(request: Request) -> ConfigWorker:
    """Воркер генерации конфигов. Нужен ручкам, после которых его пул устарел."""
    return request.app.state.config_worker
