"""Роутер конфигов: скачивание файла, привязка к клиенту панели, удаление строки."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.envelope import ConfigReadEnvelope, RecipientReadEnvelope, ok
from app.schemas.recipient import ConfigRead
from app.schemas.server import BindConfigIn
from app.services import config_service as cfs

router = APIRouter(prefix="/api/configs", tags=["configs"])


@router.get("/{config_id}/download")
def download_config(config_id: int, db: Session = Depends(get_db)):
    """Отдаёт файл конфига. Ответ бинарный, без обёртки ApiEnvelope."""
    config = cfs.get_config(db, config_id)
    if config.content is None:
        raise HTTPException(status_code=404, detail="Файл конфига ещё не сгенерирован")

    filename = config.download_filename

    return Response(
        content=config.content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )


@router.post("/{config_id}/bind", response_model=ConfigReadEnvelope)
def bind_config(config_id: int, payload: BindConfigIn, db: Session = Depends(get_db)):
    """Привязывает конфиг к клиенту, заведённому на панели вручную."""
    config = cfs.bind_external_client(db, config_id, payload.external_name)
    return ok(ConfigRead.model_validate(config))


@router.post("/{config_id}/unbind", response_model=RecipientReadEnvelope)
def unbind_config(config_id: int, db: Session = Depends(get_db)):
    """Снимает привязку, а лишнюю строку конфига убирает.

    Отвечаем получателем целиком, а не конфигом: строки может уже не быть, да и
    остальные при этом меняются — фронту всё равно нужен свежий список.
    """
    recipient = cfs.unbind_external_client(db, config_id)
    return ok(recipient)


@router.delete("/{config_id}", response_model=RecipientReadEnvelope)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    """Удаляет строку конфига у получателя. Клиент на панели остаётся жить."""
    recipient = cfs.delete_config(db, config_id)
    return ok(recipient)
