"""Pydantic-схемы для кампаний (входные и выходные данные API)."""

from datetime import datetime

from pydantic import BaseModel

from app.db.models import CampaignStatus


class CreateCampaign(BaseModel):
    """Тело запроса на создание кампании."""

    name: str
    subject: str
    body: str


class CloneCampaign(BaseModel):
    """Тело запроса на создание кампании по образцу прежней.

    Тема и текст по умолчанию берутся у исходной: чаще всего новая рассылка — это та
    же самая, но с добавленными людьми.
    """

    name: str
    subject: str | None = None
    body: str | None = None


class CampaignRead(BaseModel):
    """Ответ: данные кампании + необязательные счётчики прогресса."""

    id: int
    name: str
    subject: str
    body: str
    status: CampaignStatus
    created_at: datetime
    totals: dict | None = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    """Универсальный ответ операции (старт/стоп/импорт)."""

    detail: str
    campaign_id: int
