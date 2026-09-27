"""Pydantic-схемы для кампаний (входные и выходные данные API)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import CampaignStatus


class CreateCampaign(BaseModel):
    """Тело запроса на создание кампании."""

    name: str
    subject: str
    body: str
    # На какие серверы пойдёт рассылка: на них заведутся строки конфигов. Пустой список —
    # все включённые. Набор задаётся только здесь: исключить сервер после импорта значило
    # бы удалять уже заведённые строки.
    servers: list[str] = Field(default_factory=list)


class CloneCampaign(BaseModel):
    """Тело запроса на создание кампании по образцу прежней.

    Тема и текст по умолчанию берутся у исходной: чаще всего новая рассылка — это та
    же самая, но с добавленными людьми.
    """

    name: str
    subject: str | None = None
    body: str | None = None


class UpdateCampaign(BaseModel):
    """Правка кампании до запуска: меняется только переданное."""

    name: str | None = Field(default=None, min_length=1)
    subject: str | None = Field(default=None, min_length=1)
    body: str | None = Field(default=None, min_length=1)


class CampaignRead(BaseModel):
    """Ответ: данные кампании + необязательные счётчики прогресса."""

    id: int
    name: str
    subject: str
    body: str
    status: CampaignStatus
    # Серверы рассылки; None — кампания создана до появления выбора, значит все включённые.
    servers: list[str] | None = None
    created_at: datetime
    totals: dict | None = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    """Универсальный ответ операции (старт/стоп/импорт)."""

    detail: str
    campaign_id: int
