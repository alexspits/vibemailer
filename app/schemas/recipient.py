"""Pydantic-схемы для получателей и их конфигов."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.servers import ArtifactKind
from app.db.models import ConfigStatus, RecipientStatus


class ConfigRead(BaseModel):
    """Ответ: конфиг получателя с одного сервера, без содержимого файла.

    У ссылки подписки содержимое не секретнее самой ссылки, поэтому `link` отдаём
    как есть — фронт показывает её кнопкой «скопировать».
    """

    id: int
    # Имя для получателя: в имени вложения и рядом со ссылкой.
    name: str
    # Имя клиента на самой панели. Расходится с `name`, когда клиент заведён вручную.
    panel_name: str
    seq: int
    external_name: str | None = None
    is_external: bool = False
    server_key: str
    kind: ArtifactKind
    status: ConfigStatus
    filename: str | None = None
    link: str | None = None
    size: int = 0
    error: str | None = None

    model_config = {"from_attributes": True}


class RecipientCreate(BaseModel):
    """Тело запроса на добавление одного получателя.

    `client_name` — базовое имя клиента, `count` — сколько конфигов ему нужно. Имена
    получаются нумерацией (`alice` + 3 → `alice1`, `alice2`, `alice3`), и каждое
    заводится на каждом включённом сервере.
    """

    email: str
    name: str | None = None
    client_name: str
    count: int = Field(default=1, ge=1)


class ConfigsAdd(BaseModel):
    """Тело запроса на добавление получателю ещё конфигов.

    `servers` — на каких серверах добавить; пусто означает «на всех включённых».
    Список нужен как раз для несимметричного случая: человеку нужно пять доступов на
    одном сервере и по одному на остальных — на панели это пять отдельных клиентов.
    """

    servers: list[str] | None = None
    count: int = Field(default=1, ge=1, le=20)


class ConfigsBind(BaseModel):
    """Тело запроса на привязку сразу нескольких клиентов панели к одному получателю.

    Под каждое имя заводится **свой** конфиг: у человека столько доступов, сколько
    устройств, и привязка второго клиента не должна затирать первый.
    """

    server_key: str
    names: list[str] = Field(min_length=1)


class RecipientsBulk(BaseModel):
    """Массовое добавление получателей."""

    items: list[RecipientCreate]


class RecipientRead(BaseModel):
    """Ответ: получатель со статусом отправки и списком конфигов."""

    id: int
    campaign_id: int
    email: str
    name: str | None = None
    client_name: str
    config_count: int
    status: RecipientStatus
    error: str | None = None
    sent_at: datetime | None = None
    configs: list[ConfigRead] = []

    model_config = {"from_attributes": True}
