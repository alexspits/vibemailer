"""Схемы автоподбора клиентов панели под получателей."""

from pydantic import BaseModel, Field


class SuggestClientsIn(BaseModel):
    """Тело запроса на подбор.

    `recipient_ids` пустой — подбираем всей кампании: панели опрашиваются один раз на
    запрос, поэтому разом это дешевле, чем по одному получателю.

    `hints` — подсказка для поиска, ключ строкой (id получателя), значение свободное:
    фамилия или кусок имени с панели. Нужна, когда ни почта, ни базовое имя о человеке
    ничего не говорят — `kboyko2022` против `boykokr` угадывается, а вот `user17` нет.
    """

    recipient_ids: list[int] | None = None
    hints: dict[str, str] = Field(default_factory=dict)


class ClientCandidate(BaseModel):
    """Клиент панели, похожий на получателя."""

    name: str
    # 0…1. Не вероятность, а порядок сортировки: чем выше, тем больше совпало.
    score: float
    # Отмечать ли галочкой заранее.
    suggested: bool = False
    # Кем в кампании клиент уже занят; None — свободен.
    taken_by: str | None = None


class ServerSuggestion(BaseModel):
    """Что нашлось для получателя на одном сервере.

    `error` вместо кандидатов — панель не ответила. Это не повод валить весь подбор:
    остальные серверы всё равно полезны, а привязать к недоступной панели всё равно
    нельзя.
    """

    server_key: str
    server_title: str
    candidates: list[ClientCandidate] = []
    error: str | None = None


class RecipientSuggestion(BaseModel):
    """Подбор для одного получателя по всем серверам."""

    recipient_id: int
    email: str
    client_name: str
    servers: list[ServerSuggestion] = []


class SuggestResult(BaseModel):
    recipients: list[RecipientSuggestion] = []
