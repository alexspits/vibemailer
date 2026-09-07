"""Работа с кампаниями: CRUD, прогресс."""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Campaign, CampaignStatus, Recipient
from app.schemas.campaign import CreateCampaign
from app.services import config_service as cfs


def create_campaign(db: Session, data: CreateCampaign) -> Campaign:
    campaign = Campaign(
        name=data.name,
        subject=data.subject,
        body=data.body,
        status=CampaignStatus.NEW,
    )
    db.add(campaign)
    db.commit()
    return campaign


def list_campaigns(db: Session) -> list[Campaign]:
    return db.query(Campaign).order_by(Campaign.id.desc()).all()


def get_campaign(db: Session, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return campaign


def get_progress(db: Session, campaign: Campaign) -> dict:
    """Прогресс кампании: отправка по получателям и генерация в разрезе серверов.

    Счётчики по серверам нужны интерфейсу: у каждой кнопки генерации свой прогресс,
    и общий счётчик по кампании его не показывает.
    """
    rows = (
        db.query(Recipient.status, func.count(Recipient.id))
        .filter_by(campaign_id=campaign.id)
        .group_by(Recipient.status)
        .all()
    )
    counts = {status.value: n for status, n in rows}
    return {
        "sent": counts.get("sent", 0),
        "failed": counts.get("failed", 0),
        "pending": counts.get("pending", 0),
        "total": sum(counts.values()),
        "configs_by_server": cfs.count_by_server(db, campaign.id),
    }


def set_status(db: Session, campaign: Campaign, status: CampaignStatus) -> Campaign:
    campaign.status = status
    db.commit()
    return campaign


def delete_campaign(db: Session, campaign_id: int) -> None:
    campaign = get_campaign(db, campaign_id)
    db.delete(campaign)
    db.commit()
