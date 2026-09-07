"""Общий интерфейс панелей VPN.

Панели разные — AmneziaWG, 3x-ui, wg-easy, — но воркеру от них нужно одно и то же:
завести клиента с таким-то именем и получить то, что уедет получателю. Одни панели
отдают файл `.conf`, другие — ссылку подписки; и то и другое здесь называется
артефактом.

Про БД адаптеры не знают: получают имя, возвращают артефакт. Работу с БД делает
`config_worker`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from app.core.servers import ArtifactKind
from app.services.transport import TransportError

if TYPE_CHECKING:
    from app.core.servers import ServerConfig
    from app.services.transport import Transport

log = logging.getLogger("vibe_mail.panels")


class PanelError(Exception):
    """Не удалось получить конфиг: ошибка панели, дубликат имени, кривой ответ."""


class PanelUnreachable(PanelError):
    """До панели не доехал сам запрос: нет связи, не пустил SSH, оборвалось соединение.

    Отделено от прочих ошибок ради очереди: панель, до которой нет связи, не ответит и
    на следующий конфиг, и упираться в её таймаут ещё три десятка раз незачем.
    """


@dataclass
class Artifact:
    """То, что панель выдала на имя клиента.

    Либо файл (`filename` + `content`), либо ссылка подписки (`link`) — что именно,
    говорит `kind`. Оба поля разом не заполняются.
    """

    kind: ArtifactKind
    filename: str | None = None
    content: bytes | None = None
    link: str | None = None

    @classmethod
    def file(cls, name: str, content: bytes) -> Artifact:
        return cls(kind=ArtifactKind.FILE, filename=config_filename(name), content=content)

    @classmethod
    def url(cls, link: str) -> Artifact:
        return cls(kind=ArtifactKind.LINK, link=link)


def config_filename(name: str) -> str:
    """Имя файла без путей — защита от подстановки `../` в имени конфига."""
    return f"{Path(name).name}.conf"


class PanelClient(Protocol):
    """Что умеет любая панель."""

    def ensure_client(self, name: str) -> Artifact: ...

    def fetch_client(self, name: str) -> Artifact | None: ...

    def list_client_names(self) -> list[str]: ...

    def close(self) -> None: ...


class BasePanel:
    """Общая часть адаптеров: транспорт, настройки сервера, разбор ответа.

    Клиента с уже занятым именем не создаём заново, а забираем: на серверах живут
    клиенты, заведённые руками до появления этой программы, и перевыпускать их значит
    оставить человека со старым конфигом на руках и лишним пиром на сервере. Плодить
    одноимённых пиров панели всё равно не дают.
    """

    def __init__(self, server: ServerConfig, transport: Transport) -> None:
        self.server = server
        self.transport = transport

    # ------------------------------------------------------------------ #
    # Вспомогательное
    # ------------------------------------------------------------------ #

    def _auth_headers(self) -> dict[str, str]:
        """Заголовки авторизации панели. Переопределяется адаптером."""
        return {}

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        form_body: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        """Запрос к панели с уже подставленной авторизацией."""
        all_headers = {**self._auth_headers(), **(headers or {})}

        try:
            return self.transport.request(
                method,
                path,
                headers=all_headers,
                json_body=json_body,
                form_body=form_body,
            )
        except TransportError as exc:
            raise PanelUnreachable(str(exc)) from exc

    # ------------------------------------------------------------------ #
    # Публичное API
    # ------------------------------------------------------------------ #

    def ensure_client(self, name: str) -> Artifact:
        """Артефакт для имени: забираем существующего клиента либо заводим нового."""
        existing = self.fetch_client(name)

        if existing is not None:
            log.info(
                "Клиент %s уже есть на %s — берём существующий, не создаём заново",
                name,
                self.server.key,
            )
            return existing

        return self._create_client(name)

    def fetch_client(self, name: str) -> Artifact | None:
        """Артефакт уже заведённого клиента либо None. Переопределяется адаптером."""
        raise NotImplementedError

    def _create_client(self, name: str) -> Artifact:  # pragma: no cover - переопределяется
        raise NotImplementedError

    def list_client_names(self) -> list[str]:  # pragma: no cover - переопределяется
        raise NotImplementedError

    def close(self) -> None:
        self.transport.close()
