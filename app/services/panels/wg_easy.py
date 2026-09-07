"""WireGuard Easy (v15): конфиг-файл на клиента.

Авторизация — HTTP Basic тем же логином и паролем, что и в веб-морде. Если в панели
включена двухфакторка, API не работает вовсе — это ограничение самой wg-easy, и
единственное лечение — выключить 2FA у пользователя, под которым ходим.

В отличие от AmneziaWG, файл забирается вторым запросом: `POST /api/client` создаёт
клиента и возвращает только его id, а текст конфига отдаёт
`GET /api/client/{id}/configuration`.

API v14 (cookie-сессия через `/api/session` и пути `/api/wireguard/client`) здесь
намеренно не поддержан — на наших серверах его нет.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.services.panels.base import Artifact, BasePanel, PanelError
from app.services.transport import basic_auth_header

if TYPE_CHECKING:
    from app.services.transport import Response

log = logging.getLogger("vibe_mail.panels.wg_easy")

# Как разные сборки wg-easy называют id клиента в ответе на создание.
ID_FIELDS = ("id", "clientId")


class WgEasyPanel(BasePanel):
    """Клиенты wg-easy v15 через REST API."""

    def _auth_headers(self) -> dict[str, str]:
        return basic_auth_header(self.server.auth.username, self.server.auth.password)

    # ------------------------------------------------------------------ #
    # Внутреннее
    # ------------------------------------------------------------------ #

    def _call(self, method: str, path: str, json_body: object | None = None) -> Response:
        """Запрос с проверкой кода ответа, но без разбора тела."""
        response = self._request(method, path, json_body=json_body)

        if response.status == 401:
            raise PanelError(
                f"Панель {self.server.title} не приняла логин и пароль. "
                "Если у пользователя включена 2FA, API работать не будет."
            )

        if not response.is_ok:
            raise PanelError(
                f"Панель {self.server.title} ответила {response.status}: {response.body[:200]}"
            )

        return response

    def _api(self, method: str, path: str, json_body: object | None = None) -> object:
        return self._call(method, path, json_body).json()

    # ------------------------------------------------------------------ #
    # Публичное API
    # ------------------------------------------------------------------ #

    def _clients(self) -> list[dict]:
        clients = self._api("GET", "/api/client")

        if not isinstance(clients, list):
            raise PanelError("Панель вернула неожиданный ответ на список клиентов")

        return clients

    def list_client_names(self) -> list[str]:
        return [client["name"] for client in self._clients()]

    def fetch_client(self, name: str) -> Artifact | None:
        """Конфиг уже заведённого клиента. Панель отдаёт его по id, поэтому сперва
        находим клиента в списке."""
        found = next((c for c in self._clients() if c.get("name") == name), None)

        if found is None:
            return None

        return Artifact.file(name, self._fetch_configuration(found["id"], name))

    def _fetch_configuration(self, client_id: object, name: str) -> bytes:
        """Текст .conf созданного клиента. Ответ не JSON, а сам файл."""
        response = self._request("GET", f"/api/client/{client_id}/configuration")

        if not response.is_ok:
            raise PanelError(
                f"Не удалось забрать конфиг {name} с {self.server.title}: "
                f"{response.status} {response.body[:200]}"
            )

        return response.body.encode()

    @staticmethod
    def _created_id(body: str) -> object | None:
        """id созданного клиента из ответа на создание, если он там есть.

        Поле зовётся по-разному от сборки к сборке, а иные версии на создание отвечают
        пустым телом — поэтому «не нашли» здесь не ошибка, а повод спросить список.
        """
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        return next((payload[field] for field in ID_FIELDS if payload.get(field)), None)

    def _lookup_id(self, name: str) -> object:
        """id клиента по имени — запасной путь, когда создание его не вернуло."""
        found = next((c for c in self._clients() if c.get("name") == name), None)

        if found is None or not found.get("id"):
            raise PanelError(
                f"Панель {self.server.title} создала клиента {name}, но его id "
                "не нашёлся ни в ответе, ни в списке клиентов"
            )

        return found["id"]

    def _create_client(self, name: str) -> Artifact:
        # expiresAt обязателен в схеме, но допускает null — бессрочный клиент.
        created = self._call("POST", "/api/client", {"name": name, "expiresAt": None})
        client_id = self._created_id(created.body) or self._lookup_id(name)

        content = self._fetch_configuration(client_id, name)

        log.info("Клиент %s создан на %s", name, self.server.key)
        return Artifact.file(name, content)
