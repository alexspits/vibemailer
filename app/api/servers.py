"""Роутер VPN-серверов: список, проверка доступности и правка самого списка.

Список серверов живёт в `servers.yml`, поэтому добавление, удаление и включение —
это запись в файл. Кеш процесса и пул соединений воркера после такой записи
устаревают, и обновить их надо здесь: воркер живёт в состоянии приложения, а сервисы
про него не знают.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_config_worker, get_db
from app.schemas.envelope import (
    ListPanelClientsEnvelope,
    ListServerReadEnvelope,
    ServerCheckEnvelope,
    ServerDeletedEnvelope,
    ServerReadEnvelope,
    ok,
)
from app.schemas.server import ServerCreate, ServerDeleted, UpdateServer
from app.services import server_service as srv
from app.services.config_worker import ConfigWorker

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.get("", response_model=ListServerReadEnvelope)
def list_servers(db: Session = Depends(get_db)):
    """Все серверы из конфига, включая выключенные — фронт покажет их неактивными."""
    return ok(srv.read_servers(db))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ServerReadEnvelope)
def add_server(
    data: ServerCreate,
    worker: ConfigWorker = Depends(get_config_worker),
):
    """Дописывает сервер в `servers.yml`. Доступы приезжают сюда и наружу не возвращаются."""
    server = srv.add_server(data)
    worker.forget_panels()

    return ok(server)


@router.patch("/{server_key}", response_model=ServerReadEnvelope)
def update_server(
    server_key: str,
    data: UpdateServer,
    db: Session = Depends(get_db),
    worker: ConfigWorker = Depends(get_config_worker),
):
    """Включает сервер в рассылки по умолчанию или исключает из них."""
    server = srv.set_server_enabled(db, server_key, data.enabled)
    worker.forget_panels()

    return ok(server)


@router.delete("/{server_key}", response_model=ServerDeletedEnvelope)
def delete_server(
    server_key: str,
    force: bool = False,
    db: Session = Depends(get_db),
    worker: ConfigWorker = Depends(get_config_worker),
):
    """Убирает сервер из конфига.

    Строки конфигов в прошлых рассылках остаются: это история того, что людям ушло.
    Пока они есть, удаление требует `force` — иначе это происходило бы незаметно.
    """
    left = srv.remove_server(db, server_key, force)
    worker.forget_panels()

    detail = (
        f"Сервер {server_key} удалён, конфигов без сервера осталось: {left}"
        if left
        else f"Сервер {server_key} удалён"
    )

    return ok(ServerDeleted(detail=detail, key=server_key))


@router.post("/{server_key}/check", response_model=ServerCheckEnvelope)
def check_server(server_key: str):
    """Проверяет связь с панелью и читает список клиентов. Ничего не меняет.

    POST, а не GET: ручка поднимает SSH-соединение или сессию панели, и кешировать или
    предзагружать такое браузеру незачем.
    """
    return ok(srv.check_server(server_key))


@router.get("/{server_key}/clients", response_model=ListPanelClientsEnvelope)
def list_panel_clients(server_key: str):
    """Имена клиентов, которые сейчас есть на панели.

    Ходит на живую панель, поэтому отвечает не мгновенно — интерфейс запрашивает это
    только когда человек открывает привязку.
    """
    return ok(srv.list_panel_clients(server_key))
