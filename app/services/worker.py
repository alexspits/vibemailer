"""Фоновый поток отправки писем.

Запускается вместе с приложением (через lifespan) и последовательно обрабатывает
кампании со статусом IN_PROGRESS: берёт pending-получателей, отправляет через
MailSender, обновляет статусы в БД. БД — источник правды, поэтому при старте
процесса «зависшие» in_progress-кампании подхватываются автоматически (возобновление).
"""

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Campaign, CampaignStatus, Recipient, RecipientStatus
from app.db.session import SessionLocal
from app.services.mail_sender import MailSender

log = logging.getLogger("vibe_mail.worker")

# Пауза между опросами БД, секунды.
IDLE_INTERVAL = 1.0


class Worker:
    """Потоковый воркер отправки писем."""

    def __init__(self, settings: Settings, mail_sender: MailSender) -> None:
        self.settings = settings
        self.mail_sender = mail_sender
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)

    # ------------------------------------------------------------------ #
    # Цикл
    # ------------------------------------------------------------------ #

    def _loop(self) -> None:
        log.info("Воркер отправки запущен")
        while not self._stop.is_set():
            self._tick()
            self._stop.wait(IDLE_INTERVAL)
        log.info("Воркер отправки остановлен")

    def _tick(self) -> None:
        """Один проход по всем работающим кампаниям."""
        try:
            with SessionLocal() as db:
                self._process_running_campaigns(db)
        except Exception:  # воркер не должен падать по одной ошибке
            log.exception("Ошибка в цикле воркера, повтор через секунду")

    def _process_running_campaigns(self, db: Session) -> None:
        for campaign in self._running_campaigns(db):
            if self._stop.is_set():
                return
            self._process_campaign(db, campaign)

    def _process_campaign(self, db: Session, campaign: Campaign) -> None:
        """Отправляет очередную порцию писем кампании либо закрывает её."""
        pending = self._pending_recipients(db, campaign.id)
        if not pending:
            self._finish_campaign(db, campaign)
            return

        for recipient in pending:
            # Кампанию могли остановить из HTTP-запроса, пока идёт пачка, поэтому статус
            # перечитываем перед каждым письмом: иначе stop сработал бы только со
            # следующего тика, то есть после рассылки всей пачки.
            if self._stop.is_set() or not self._is_running(db, campaign.id):
                return
            self._send_one(db, campaign, recipient)
            # Пауза между письмами; прерывается сразу при остановке воркера.
            self._stop.wait(self.settings.DEFAULT_DELAY)

    def _finish_campaign(self, db: Session, campaign: Campaign) -> None:
        """Терминальный статус кампании: DONE либо DONE_WITH_ERRORS, если были падения."""
        has_failed = self._has_failed(db, campaign.id)
        campaign.status = CampaignStatus.DONE_WITH_ERRORS if has_failed else CampaignStatus.DONE
        db.commit()
        log.info(
            "Кампания %s завершена (%s)",
            campaign.id,
            "есть ошибки отправки" if has_failed else "все письма обработаны",
        )

    def _send_one(self, db: Session, campaign: Campaign, recipient: Recipient) -> None:
        """Одно письмо: отправка и фиксация результата в БД."""
        ok, err = self.mail_sender.send(campaign, recipient, recipient.configs)

        recipient.status = RecipientStatus.SENT if ok else RecipientStatus.FAILED
        recipient.error = err
        recipient.sent_at = datetime.now(UTC).replace(tzinfo=None) if ok else None
        db.commit()

        if ok:
            log.info("[%s] Отправлено: %s", campaign.id, recipient.email)
        else:
            log.error("[%s] Ошибка для %s: %s", campaign.id, recipient.email, err)

    # ------------------------------------------------------------------ #
    # Запросы
    # ------------------------------------------------------------------ #

    @staticmethod
    def _running_campaigns(db: Session) -> list[Campaign]:
        return db.query(Campaign).filter_by(status=CampaignStatus.IN_PROGRESS).all()

    @staticmethod
    def _is_running(db: Session, campaign_id: int) -> bool:
        """Ещё ли кампания в работе — свежим запросом, мимо кеша сессии."""
        status = db.query(Campaign.status).filter_by(id=campaign_id).scalar()
        return status == CampaignStatus.IN_PROGRESS

    @staticmethod
    def _pending_recipients(db: Session, campaign_id: int) -> list[Recipient]:
        return (
            db.query(Recipient)
            .filter_by(campaign_id=campaign_id, status=RecipientStatus.PENDING)
            .order_by(Recipient.id)
            .all()
        )

    @staticmethod
    def _has_failed(db: Session, campaign_id: int) -> bool:
        return (
            db.query(Recipient)
            .filter_by(campaign_id=campaign_id, status=RecipientStatus.FAILED)
            .first()
            is not None
        )
