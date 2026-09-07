"""Доступ к списку VPN-серверов из остального кода.

Тонкая обёртка над `app.core.servers`: подставляет путь к файлу из настроек и
переводит «сервера с таким ключом нет» в честный HTTP-404. Список сам по себе
кешируется, файл читается один раз за процесс.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.servers import ServerConfig, get_servers
from app.services.panels import PanelError, build_panel

log = logging.getLogger("vibe_mail.server_service")


def all_servers() -> list[ServerConfig]:
    """Все серверы из конфига, включая выключенные."""
    return get_servers(get_settings().VPN_SERVERS_FILE).servers


def enabled_servers() -> list[ServerConfig]:
    """Серверы, на которых заводятся конфиги."""
    return get_servers(get_settings().VPN_SERVERS_FILE).enabled


def enabled_keys() -> list[str]:
    return [server.key for server in enabled_servers()]


def find_server(key: str) -> ServerConfig | None:
    """Сервер по ключу либо None. Для фонового кода, которому HTTP-исключения ни к чему."""
    return next((server for server in all_servers() if server.key == key), None)


def get_server(key: str) -> ServerConfig:
    """Сервер по ключу; 404, если такого в конфиге нет."""
    server = find_server(key)
    if server is None:
        raise HTTPException(status_code=404, detail=f"Сервер {key} не найден в конфиге")
    return server


def resolve_keys(keys: list[str] | None) -> list[str]:
    """Ключи серверов для операции: пустой список или None — значит все включённые.

    Явно перечисленные проверяются: опечатка в ключе не должна тихо превращаться
    в «ничего не сделали».
    """
    enabled = enabled_keys()

    if not keys:
        return enabled

    unknown = [key for key in keys if key not in enabled]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестные или выключенные серверы: {', '.join(unknown)}",
        )

    return keys


def list_panel_clients(key: str) -> list[str]:
    """Имена клиентов, которые сейчас есть на панели этого сервера.

    Нужно интерфейсу привязки: клиентов, заведённых руками, надо показать человеку,
    чтобы он сопоставил их с получателями. Соединение здесь одноразовое — это редкое
    действие из интерфейса, а не горячий путь генерации.
    """
    server = get_server(key)
    panel = build_panel(server)

    try:
        return sorted(panel.list_client_names())
    except PanelError as exc:
        raise HTTPException(status_code=502, detail=f"Панель {server.title}: {exc}") from exc
    finally:
        panel.close()
