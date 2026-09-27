"""Pydantic-схемы VPN-серверов.

Наружу отдаётся только то, что нужно интерфейсу: ключ, название, тип панели и артефакта,
куда за ним ходим и сколько на нём конфигов. Доступы (SSH, токены, пароли) не покидают
бэкенд — обратно, на добавление сервера, они приезжают, но никогда не читаются.
"""

from pydantic import BaseModel

from app.core.servers import ArtifactKind, PanelKind, ServerConfig, TransportKind


class ServerRead(BaseModel):
    """Ответ: один настроенный сервер."""

    key: str
    title: str
    panel: PanelKind
    transport: TransportKind
    artifact: ArtifactKind
    enabled: bool
    # Куда и чем ходим: `ssh de2 → http://127.0.0.1:8080` либо просто адрес панели.
    where: str
    # Сколько строк конфигов ссылается на этот ключ и сколько из них ещё без артефакта.
    # Первое нужно предупреждению при удалении сервера, второе — при выключении.
    configs: int = 0
    unfinished: int = 0


class ServerCreate(ServerConfig):
    """Тело запроса на добавление сервера.

    Ровно тот же набор полей, что и в `servers.yml`: проверки («при transport=ssh нужен
    блок ssh», «для 3x-ui нужен inbound_ids») уже написаны валидатором модели, и
    дублировать их отдельной схемой значило бы разойтись с файлом при первой же правке.
    """


class UpdateServer(BaseModel):
    """Тело запроса на включение сервера в рассылки по умолчанию или исключение из них."""

    enabled: bool


class ServerCheck(BaseModel):
    """Результат проверки доступности панели. Ничего на сервере не меняет."""

    key: str
    ok: bool
    # Сколько клиентов на панели и первые их имена — видно, что читаем ту самую панель.
    clients: int | None = None
    sample: list[str] = []
    # AmneziaWG: версия протокола, которую получат новые клиенты.
    protocol: str = ""
    # 3x-ui: база ссылки подписки.
    subscription: str = ""
    # Нашёлся ли конкретный клиент — спрашивает только `check_servers.py --name`.
    client_found: bool | None = None
    error: str = ""
    # Подсказка к типовой ошибке настройки; пусто — совет не нашёлся.
    hint: str = ""
    elapsed_ms: int = 0


class ServerDeleted(BaseModel):
    """Ответ на удаление сервера из конфига."""

    detail: str
    key: str


class GenerateConfigsIn(BaseModel):
    """Тело запроса на генерацию: на каких серверах.

    Пустой список (или отсутствующее тело) — все серверы рассылки, то есть кнопка
    «Сгенерировать все».
    """

    servers: list[str] = []


class BindConfigIn(BaseModel):
    """Тело запроса на привязку конфига к клиенту, заведённому на панели вручную."""

    external_name: str
