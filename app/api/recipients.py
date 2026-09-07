"""Роутер получателей: удаление и добавление конфигов."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.envelope import RecipientReadEnvelope, ok
from app.schemas.recipient import ConfigsAdd, ConfigsBind
from app.services import config_service as cfs
from app.services import recipient_service as rs

router = APIRouter(prefix="/api/recipients", tags=["recipients"])


@router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipient(recipient_id: int, db: Session = Depends(get_db)):
    recipient = rs.get_recipient(db, recipient_id)
    db.delete(recipient)
    db.commit()


@router.post(
    "/{recipient_id}/configs",
    status_code=status.HTTP_201_CREATED,
    response_model=RecipientReadEnvelope,
)
def add_configs(
    recipient_id: int,
    payload: ConfigsAdd | None = None,
    db: Session = Depends(get_db),
):
    """Добавляет получателю ещё конфиги. Генерацию по-прежнему запускает кнопка.

    Конфиг создаётся пустым (PENDING) — это же нужно и для привязки: привязать можно
    только к существующей строке конфига, а у человека с пятью доступами на панели
    строк должно быть пять.
    """
    payload = payload or ConfigsAdd()
    recipient = rs.add_configs(db, recipient_id, payload.servers, payload.count)

    return ok(recipient)


@router.post(
    "/{recipient_id}/configs/bind",
    status_code=status.HTTP_201_CREATED,
    response_model=RecipientReadEnvelope,
)
def bind_new_configs(recipient_id: int, payload: ConfigsBind, db: Session = Depends(get_db)):
    """Привязывает получателю сразу несколько клиентов панели — по конфигу на каждого."""
    recipient = cfs.bind_new_clients(db, recipient_id, payload.server_key, payload.names)

    return ok(recipient)
