"""Работа с кампаниями: CRUD, прогресс."""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Campaign,
    CampaignStatus,
    Config,
    ConfigStatus,
    Recipient,
    RecipientStatus,
)
from app.schemas.campaign import CloneCampaign, CreateCampaign
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


def clone_campaign(db: Session, campaign_id: int, data: CloneCampaign) -> Campaign:
    """Создаёт кампанию по образцу прежней: те же люди, те же привязки.

    Копируются получатели и строки их конфигов вместе с привязками к клиентам панелей,
    но без самих конфигов: содержимое и ссылки не переносятся, строки создаются
    пустыми. Так и правильнее — конфиг заберётся с панели заново, и если там что-то
    изменилось, человек получит актуальное, а не копию прошлогоднего файла.

    Привязки между кампаниями сами по себе не наследуются: `external_name` живёт на
    строке конфига, а она принадлежит получателю конкретной кампании. Поэтому
    копирование здесь — единственный способ не расставлять их заново руками.
    """
    source = get_campaign(db, campaign_id)

    campaign = Campaign(
        name=data.name,
        subject=data.subject if data.subject is not None else source.subject,
        body=data.body if data.body is not None else source.body,
        status=CampaignStatus.NEW,
    )
    db.add(campaign)
    db.flush()

    for recipient in source.recipients:
        copy = Recipient(
            campaign_id=campaign.id,
            email=recipient.email,
            name=recipient.name,
            client_name=recipient.client_name,
            config_count=recipient.config_count,
            status=RecipientStatus.PENDING,
        )
        copy.configs = [
            Config(
                seq=config.seq,
                server_key=config.server_key,
                kind=config.kind,
                external_name=config.external_name,
                status=ConfigStatus.PENDING,
            )
            for config in recipient.configs
        ]
        db.add(copy)

    db.commit()
    db.refresh(campaign)

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
