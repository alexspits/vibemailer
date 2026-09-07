"""Pydantic-схемы VPN-серверов.

Наружу отдаётся только то, что нужно интерфейсу для кнопок генерации: ключ, название
и тип артефакта. Доступы (SSH, токены, пароли) не покидают бэкенд.
"""

from pydantic import BaseModel

from app.core.servers import ArtifactKind, PanelKind


class ServerRead(BaseModel):
    """Ответ: один настроенный сервер."""

    key: str
    title: str
    panel: PanelKind
    artifact: ArtifactKind
    enabled: bool


class GenerateConfigsIn(BaseModel):
    """Тело запроса на генерацию: на каких серверах.

    Пустой список (или отсутствующее тело) — все включённые серверы, то есть кнопка
    «Сгенерировать все».
    """

    servers: list[str] = []


class BindConfigIn(BaseModel):
    """Тело запроса на привязку конфига к клиенту, заведённому на панели вручную."""

    external_name: str
