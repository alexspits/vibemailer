"""Роутер VPN-серверов: фронту нужен их список, чтобы нарисовать кнопки генерации."""

from fastapi import APIRouter

from app.schemas.envelope import ListPanelClientsEnvelope, ListServerReadEnvelope, ok
from app.schemas.server import ServerRead
from app.services import server_service as srv

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.get("", response_model=ListServerReadEnvelope)
def list_servers():
    """Все серверы из конфига, включая выключенные — фронт покажет их неактивными."""
    return ok(
        [
            ServerRead(
                key=server.key,
                title=server.title,
                panel=server.panel,
                artifact=server.artifact_kind,
                enabled=server.enabled,
            )
            for server in srv.all_servers()
        ]
    )


@router.get("/{server_key}/clients", response_model=ListPanelClientsEnvelope)
def list_panel_clients(server_key: str):
    """Имена клиентов, которые сейчас есть на панели.

    Ходит на живую панель, поэтому отвечает не мгновенно — интерфейс запрашивает это
    только когда человек открывает привязку.
    """
    return ok(srv.list_panel_clients(server_key))
