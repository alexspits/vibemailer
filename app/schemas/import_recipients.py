"""Pydantic-схемы импорта получателей из вставленного списка."""

from pydantic import BaseModel


class RecipientsImportText(BaseModel):
    """Тело запроса: вставленный из таблицы текст (две колонки через таб)."""

    text: str


class ImportRowProblem(BaseModel):
    """Строка, которую не удалось разобрать."""

    line: int
    raw: str
    reason: str


class ImportGroup(BaseModel):
    """Одно письмо: получатель, его базовое имя и сколько конфигов ему нужно.

    `existing_client_name` заполняется, если получатель в кампании уже есть: имя
    менять не будем, и в предпросмотре видно, какое останется.
    """

    email: str
    client_name: str
    existing_client_name: str | None = None
    is_existing: bool = False
    # Сколько конфигов будет у получателя после импорта и сколько было.
    count: int = 1
    existing_count: int = 0
    # Сколько строк конфигов реально заведётся (по всем серверам).
    new_configs: int = 0
    # Ключи серверов, которых коснётся импорт.
    servers: list[str] = []
    # Имена конфигов, которые появятся: alice-1, alice-2, …
    new_names: list[str] = []
    # Ключ сервера → имя клиента на панели, к которому привяжется первый конфиг.
    bindings: dict[str, str] = {}


class ImportPreview(BaseModel):
    """Предпросмотр импорта: что получится, если сохранить."""

    groups: list[ImportGroup]
    problems: list[ImportRowProblem] = []
    total_rows: int
    total_recipients: int
    total_configs: int


class ImportResult(BaseModel):
    """Итог импорта."""

    created_recipients: int
    updated_recipients: int
    created_configs: int
    problems: list[ImportRowProblem] = []
