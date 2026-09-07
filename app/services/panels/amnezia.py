"""AmneziaWG Web UI: конфиг-файл на клиента.

`POST /api/servers/{id}/clients` одним вызовом создаёт клиента и возвращает текст
его конфига. У уже существующего клиента конфиг лежит отдельно, за
`GET /api/servers/{id}/clients/{client_id}/config`: в списке клиентов его нет, там
только ключи и параметры обфускации.

Переименования клиентов в этой панели нет, поэтому имена здесь только заводятся.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.panels.base import Artifact, BasePanel, PanelError
from app.services.transport import basic_auth_header

if TYPE_CHECKING:
    from app.core.servers import ServerConfig
    from app.services.transport import Transport

log = logging.getLogger("vibe_mail.panels.amnezia")


class AmneziaPanel(BasePanel):
    """Клиенты AmneziaWG через API панели."""

    def __init__(self, server: ServerConfig, transport: Transport) -> None:
        super().__init__(server, transport)
        self._server_id: str | None = server.panel_server_id or None

    def _auth_headers(self) -> dict[str, str]:
        return basic_auth_header(self.server.auth.username, self.server.auth.password)

    # ------------------------------------------------------------------ #
    # Внутреннее
    # ------------------------------------------------------------------ #

    def _api(self, method: str, path: str, json_body: object | None = None) -> object:
        response = self._request(method, path, json_body=json_body)

        if not response.is_ok:
            raise PanelError(
                f"Панель {self.server.title} ответила {response.status}: {response.body[:200]}"
            )

        return response.json()

    @staticmethod
    def _pick_single_server(servers: object) -> str:
        """ID единственного сервера панели; иначе — объясняющая ошибка."""
        if not isinstance(servers, list) or not servers:
            raise PanelError("На панели нет ни одного сервера")

        if len(servers) > 1:
            names = ", ".join(f"{s.get('name')} ({s.get('id')})" for s in servers)
            raise PanelError(f"На панели несколько серверов, укажите panel_server_id: {names}")

        return servers[0]["id"]

    def _resolve_server_id(self) -> str:
        """ID сервера панели: из настроек либо единственный существующий."""
        if not self._server_id:
            self._server_id = self._pick_single_server(self._api("GET", "/api/servers"))
        return self._server_id

    # ------------------------------------------------------------------ #
    # Публичное API
    # ------------------------------------------------------------------ #

    def _clients(self) -> list[dict]:
        clients = self._api("GET", f"/api/servers/{self._resolve_server_id()}/clients")

        if not isinstance(clients, list):
            raise PanelError("Панель вернула неожиданный ответ на список клиентов")

        return clients

    def list_client_names(self) -> list[str]:
        return [client["name"] for client in self._clients()]

    def fetch_client(self, name: str) -> Artifact | None:
        """Конфиг уже заведённого клиента; None — такого клиента на панели нет.

        Список клиентов конфига не содержит, поэтому за ним идём вторым запросом по
        id клиента. Отдаётся он текстом, а не JSON — как файл, который панель даёт
        скачать в своём интерфейсе.
        """
        found = next((c for c in self._clients() if c.get("name") == name), None)

        if found is None:
            return None

        client_id = found.get("id")

        if not client_id:
            raise PanelError(f"Панель не назвала id клиента {name}: {found}")

        server_id = self._resolve_server_id()
        response = self._request("GET", f"/api/servers/{server_id}/clients/{client_id}/config")

        if not response.is_ok or not response.body.strip():
            raise PanelError(
                f"Панель {self.server.title} не отдала конфиг клиента {name}: "
                f"ответ {response.status}"
            )

        return Artifact.file(name, response.body.encode())

    def _create_client(self, name: str) -> Artifact:
        server_id = self._resolve_server_id()

        response = self._api("POST", f"/api/servers/{server_id}/clients", {"name": name})

        if not isinstance(response, dict) or not response.get("config"):
            # Только имена полей: в ответе лежит текст конфига с приватным ключом,
            # а ошибка сохраняется в БД и показывается в интерфейсе.
            fields = ", ".join(sorted(response)) if isinstance(response, dict) else "не объект"
            raise PanelError(f"Панель не вернула конфиг для {name} (поля ответа: {fields})")

        log.info("Клиент %s создан на %s", name, self.server.key)
        return Artifact.file(name, response["config"].encode())
