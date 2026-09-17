"""Фоновый поток генерации конфигов.

Запускается вместе с приложением (через lifespan) и обрабатывает конфиги в статусе
QUEUED: берёт по одному, заводит клиента на нужной панели и складывает результат в БД.
Источник правды — статусы в БД, поэтому процесс возобновляем: при старте «зависшие»
GENERATING возвращаются в очередь.

Серверов несколько, поэтому адаптеры панелей держатся пулом по ключу сервера: одно
SSH-соединение или HTTP-сессия на сервер живёт весь прогон очереди, а не поднимается
заново на каждый конфиг.
"""

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.servers import ArtifactKind
from app.db.models import Config, ConfigStatus
from app.db.session import SessionLocal
from app.services import server_service as srv
from app.services.panels import (
    Artifact,
    PanelClient,
    PanelError,
    PanelUnreachable,
    build_panel,
)

log = logging.getLogger("vibe_mail.config_worker")

# Пауза между опросами очереди, секунды.
IDLE_INTERVAL = 1.0


class ConfigWorker:
    """Потоковый воркер генерации конфигов."""

    def __init__(self) -> None:
        self._panels: dict[str, PanelClient] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._requeue_stuck()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        self._close_panels()

    @staticmethod
    def _requeue_stuck() -> None:
        """Возвращает в очередь конфиги, на которых процесс прервался."""
        with SessionLocal() as db:
            stuck = db.query(Config).filter_by(status=ConfigStatus.GENERATING).all()
            for config in stuck:
                config.status = ConfigStatus.QUEUED
            if stuck:
                db.commit()
                log.info("Возвращено в очередь конфигов: %d", len(stuck))

    # ------------------------------------------------------------------ #
    # Панели
    # ------------------------------------------------------------------ #

    def _panel(self, server_key: str) -> PanelClient:
        """Адаптер панели по ключу сервера; соединение переиспользуется."""
        panel = self._panels.get(server_key)

        if panel is None:
            server = srv.find_server(server_key)
            if server is None:
                raise LookupError(
                    f"Сервера {server_key} больше нет в конфиге — конфиг сгенерировать некому"
                )

            panel = build_panel(server)
            self._panels[server_key] = panel

        return panel

    def _close_panels(self) -> None:
        for server_key, panel in self._panels.items():
            try:
                panel.close()
            except Exception:  # закрытие не должно ронять остановку
                log.warning("Не удалось закрыть соединение с %s", server_key, exc_info=True)

        self._panels.clear()

    # ------------------------------------------------------------------ #
    # Цикл
    # ------------------------------------------------------------------ #

    def _loop(self) -> None:
        log.info("Воркер генерации конфигов запущен")
        while not self._stop.is_set():
            self._tick()
            self._stop.wait(IDLE_INTERVAL)
        log.info("Воркер генерации конфигов остановлен")

    def _tick(self) -> None:
        """Один проход по очереди конфигов."""
        try:
            with SessionLocal() as db:
                self._process_queued(db)
        except Exception:  # воркер не должен падать по одной ошибке
            log.exception("Ошибка в цикле воркера конфигов, повтор через секунду")

    def _process_queued(self, db: Session) -> None:
        """Проход по очереди.

        Сервер, до которого нет связи, помечается на весь проход: ждать его таймаут
        отдельно на каждом из десятков конфигов — это десятки минут впустую, а ответ
        всё равно будет тот же. Конфиги такого сервера сразу уходят в FAILED с той же
        причиной, и кнопка генерации повторит их, когда связь появится.
        """
        unreachable: dict[str, Exception] = {}

        for config in self._queued_configs(db):
            if self._stop.is_set():
                return

            known = unreachable.get(config.server_key)

            if known is not None:
                self._mark_failed(db, config, known)
                continue

            failure = self._process(db, config)

            if isinstance(failure, PanelUnreachable):
                unreachable[config.server_key] = failure

    def _process(self, db: Session, config: Config) -> Exception | None:
        """Один конфиг: QUEUED → GENERATING → READY либо FAILED.

        Заводим клиента либо забираем уже существующего: на серверах живут клиенты,
        созданные руками до появления этой программы, и перевыпускать их нельзя.
        Возвращает ошибку, если она была, — вызывающему важно отличить «панель не
        отвечает» от «панель отказала по этому конкретному имени».
        """
        # На панель идём с её именем: у привязанного вручную клиента оно короткое
        # и с человеческим именем конфига не совпадает.
        name = config.panel_name
        # Приметы строки на момент старта. Генерация идёт секундами, и за это время
        # оператор успевает отвязать, перепривязать или удалить конфиг из интерфейса.
        # Записывать результат в изменившуюся строку нельзя: там окажется доступ
        # клиента, которого в ней больше не ждут.
        identity = (config.id, config.external_name, config.seq)

        if not self._claim(db, config):
            log.info("Конфиг %s уже не в очереди — пропускаем", config.id)
            return None

        try:
            # Получение панели тоже внутри try: сервер могли убрать из servers.yml при
            # живых конфигах, и тогда исключение пролетало мимо `_mark_failed`, оставляя
            # конфиг в GENERATING навсегда — кнопка генерации такие не подхватывает.
            panel = self._panel(config.server_key)
            # Привязанного клиента только забираем: создавать под его именем нельзя.
            artifact = self._adopt(panel, name) if config.is_external else panel.ensure_client(name)
        except Exception as exc:  # noqa: BLE001 - ошибка одного конфига не рушит очередь
            self._mark_failed(db, config, exc, identity)
            return exc

        self._store_result(db, config, artifact, identity)
        return None

    @staticmethod
    def _adopt(panel: PanelClient, name: str) -> Artifact:
        """Артефакт клиента, заведённого на панели вручную. Создавать не пытаемся.

        Привязка означает «у этого человека на панели уже есть доступ, отдай его». Если
        имя не нашлось, оно почти наверняка записано неточно: на панели `LitovkaP1`, а
        в импорте `litovkap`. Завести клиента под ошибочным именем — молча сделать не
        то: человек получит новый доступ вместо своего, а на панели останется лишний
        peer, про который никто не помнит. Поэтому честно падаем.
        """
        artifact = panel.fetch_client(name)

        if artifact is None:
            raise PanelError(
                f"Привязка {name!r}: такого клиента на панели нет. Имя должно совпадать "
                f"с тем, что показывает сама панель — проверьте его "
                f"(pipenv run python check_servers.py <сервер> --name {name})."
            )

        return artifact

    # ------------------------------------------------------------------ #
    # Переходы статусов
    # ------------------------------------------------------------------ #

    @staticmethod
    def _write(db: Session, identity: tuple, statuses: tuple, values: dict) -> bool:
        """Меняет строку конфига, только если она всё ещё та же и в ожидаемом статусе.

        Условие целиком в самом UPDATE, а не проверкой перед ним: между проверкой и
        записью в другом потоке помещается всё то же самое, от чего мы защищаемся.
        Возвращает False, если строку успели изменить или удалить.
        """
        config_id, external, seq = identity

        query = db.query(Config).filter(
            Config.id == config_id,
            Config.status.in_(statuses),
            Config.seq == seq,
            Config.external_name.is_(None)
            if external is None
            else Config.external_name == external,
        )

        changed = query.update(values, synchronize_session=False)
        db.commit()

        return bool(changed)

    def _claim(self, db: Session, config: Config) -> bool:
        """Забирает конфиг из очереди себе. False — его уже нет или он не в очереди."""
        identity = (config.id, config.external_name, config.seq)

        return self._write(
            db, identity, (ConfigStatus.QUEUED,), {Config.status: ConfigStatus.GENERATING}
        )

    def _mark_failed(self, db: Session, config: Config, exc: Exception, identity=None) -> None:
        identity = identity or (config.id, config.external_name, config.seq)
        statuses = (ConfigStatus.GENERATING, ConfigStatus.QUEUED)

        written = self._write(
            db, identity, statuses, {Config.status: ConfigStatus.FAILED, Config.error: str(exc)}
        )

        if not written:
            log.info("Конфиг %s изменился, пока шла генерация — ошибку не записываем", config.id)
            return

        log.error(
            "Не удалось получить конфиг %s на сервере %s",
            config.name,
            config.server_key,
            exc_info=exc,
        )

    def _store_result(
        self, db: Session, config: Config, artifact: Artifact, identity: tuple
    ) -> None:
        """Кладёт в БД то, что вернула панель: файл либо ссылку подписки."""
        values = {
            Config.kind: artifact.kind,
            Config.status: ConfigStatus.READY,
            Config.error: None,
            Config.generated_at: datetime.now(UTC).replace(tzinfo=None),
        }

        if artifact.kind is ArtifactKind.LINK:
            values |= {
                Config.link: artifact.link,
                Config.filename: None,
                Config.content: None,
                Config.size: 0,
            }
        else:
            values |= {
                Config.filename: artifact.filename,
                Config.content: artifact.content,
                Config.size: len(artifact.content or b""),
                Config.link: None,
            }

        if not self._write(db, identity, (ConfigStatus.GENERATING,), values):
            # Пока ходили на панель, строку отвязали, перепривязали или удалили.
            # Записать в неё этот артефакт — значит отдать человеку доступ клиента,
            # которого в этой строке больше не ждут.
            log.warning("Конфиг %s изменился, пока шла генерация — результат отброшен", config.id)

    # ------------------------------------------------------------------ #
    # Запросы
    # ------------------------------------------------------------------ #

    @staticmethod
    def _queued_configs(db: Session) -> list[Config]:
        return db.query(Config).filter_by(status=ConfigStatus.QUEUED).order_by(Config.id).all()
