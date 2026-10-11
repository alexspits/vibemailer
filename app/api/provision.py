"""Роутер поднятия нового сервера: запуск плейбука и слежение за прогоном.

Прогон идёт минутами, поэтому запуск отдаёт 202 и строку прогона, а страница ходит сюда
за состоянием и за куском лога. Сам подпроцесс живёт в `ProvisionRunner` из состояния
приложения — как и воркеры, сервисы про него не знают.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_provision_runner
from app.db.models import ProvisionRun
from app.schemas.envelope import (
    ListProvisionRunEnvelope,
    ProvisionDefaultsEnvelope,
    ProvisionRunEnvelope,
    ok,
)
from app.schemas.provision import ProvisionIn
from app.services import provision_service as provision
from app.services.provision_runner import ProvisionRunner

router = APIRouter(prefix="/api/provision", tags=["provision"])

# Сколько прогонов показываем в истории: страница рисует последний, остальные — чтобы
# было видно, что до него было.
HISTORY_LIMIT = 10


def _run_or_404(db: Session, run_id: int) -> ProvisionRun:
    run = db.get(ProvisionRun, run_id)

    if run is None:
        raise HTTPException(status_code=404, detail=f"Прогон {run_id} не найден")

    return run


@router.get("/defaults", response_model=ProvisionDefaultsEnvelope)
def provision_defaults():
    """Значения для формы и ответ на вопрос, можно ли вообще поднимать серверы."""
    return ok(provision.defaults())


@router.get("", response_model=ListProvisionRunEnvelope)
def list_runs(
    db: Session = Depends(get_db),
    runner: ProvisionRunner = Depends(get_provision_runner),
):
    """Последние прогоны, свежие сверху. Логи здесь не отдаём — страница тянет один."""
    runs = db.query(ProvisionRun).order_by(ProvisionRun.id.desc()).limit(HISTORY_LIMIT).all()

    return ok([
        provision.read_run(run, password=runner.secret(run.id), with_log=False) for run in runs
    ])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ProvisionRunEnvelope)
def start_run(
    data: ProvisionIn,
    db: Session = Depends(get_db),
    runner: ProvisionRunner = Depends(get_provision_runner),
):
    """Запускает плейбук по новому серверу.

    Доступы для первого входа уезжают в файлы прогона с правами 600 и удаляются вместе
    с ним: в базе и в логе их нет. 409 — если прогон уже идёт: одновременно гоняем один.
    """
    run = runner.launch(db, data)

    return ok(provision.read_run(run, password=runner.secret(run.id)))


@router.get("/{run_id}", response_model=ProvisionRunEnvelope)
def get_run(
    run_id: int,
    offset: int = 0,
    db: Session = Depends(get_db),
    runner: ProvisionRunner = Depends(get_provision_runner),
):
    """Состояние прогона и кусок лога после `offset`.

    Смещение страница присылает то, которое получила в прошлый раз, и дописывает
    пришедшее в конец — иначе лог переливался бы целиком на каждом тике полинга.
    """
    run = _run_or_404(db, run_id)

    return ok(provision.read_run(run, offset=offset, password=runner.secret(run.id)))


@router.post("/{run_id}/cancel", response_model=ProvisionRunEnvelope)
def cancel_run(
    run_id: int,
    db: Session = Depends(get_db),
    runner: ProvisionRunner = Depends(get_provision_runner),
):
    """Прерывает прогон. Аварийная кнопка: сервер может остаться недонастроенным."""
    run = _run_or_404(db, run_id)
    runner.cancel(run.id)
    db.refresh(run)

    return ok(provision.read_run(run, password=runner.secret(run.id)))
