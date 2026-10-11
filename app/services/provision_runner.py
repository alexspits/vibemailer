"""Прогон плейбука: подпроцесс `ansible-playbook` и поток, который читает его вывод.

Прогон идёт минутами — полное обновление пакетов, установка docker, смена порта SSH,
в конце возможная перезагрузка, — поэтому запуск отдаёт 202, а страница следит за
состоянием по строке в базе и по логу на диске.

Одновременно идёт **один** прогон: два параллельных `apt dist-upgrade` ничего не
ускоряют, а тем же замком ловится двойной клик по кнопке.
"""

from __future__ import annotations

import contextlib
import datetime
import logging
import os
import shlex
import signal
import subprocess
import threading
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.core.config import get_settings
from app.db.models import ProvisionRun, ProvisionStatus
from app.db.session import SessionLocal
from app.services import provision_service as provision

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.schemas.provision import ProvisionIn
    from app.services.config_worker import ConfigWorker
    from app.services.provision_service import PreparedRun

log = logging.getLogger("vibe_mail.provision_runner")

# Сколько ждём, пока прерванный плейбук закроется, прежде чем добить его.
KILL_GRACE = 10

CANCELLED_HINT = (
    "Сервер мог остаться недонастроенным — плейбук идемпотентен, "
    "повторный запуск доведёт настройку."
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class ProvisionRunner:
    """Запускает плейбуки по одному и следит за текущим прогоном."""

    def __init__(self, config_worker: ConfigWorker) -> None:
        self._config_worker = config_worker
        # Короткие критические секции: кто сейчас идёт и жив ли подпроцесс.
        self._guard = threading.Lock()
        self._current_id: int | None = None
        self._process: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._timer: threading.Timer | None = None
        # Пусто — прогон никто не прерывал; иначе здесь причина для строки прогона.
        self._abort_reason = ""
        # Пароль панели последнего прогона: страница показывает его один раз. В базу он
        # не ложится, а в servers.yml попадает только по успеху.
        self._secrets: dict[int, str] = {}

    # ------------------------------------------------------------------ #
    # Жизненный цикл
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Закрывает прогоны, оборвавшиеся вместе с прошлым процессом.

        Подпроцесс живёт не дольше приложения, поэтому строка в состоянии «идёт»
        после перезапуска — это всегда прерванный прогон, а не забытый.
        """
        with SessionLocal() as db:
            stale = db.query(ProvisionRun).filter_by(status=ProvisionStatus.RUNNING).all()

            for run in stale:
                run.status = ProvisionStatus.FAILED
                run.error = f"Прогон прервался вместе с приложением. {CANCELLED_HINT}"
                run.finished_at = _now()

            if stale:
                db.commit()
                log.info("Закрыто прерванных прогонов: %d", len(stale))

    def stop(self) -> None:
        """Прерывает текущий прогон: приложение уходит, подпроцесс не должен жить."""
        if self._current_id is None:
            return

        log.warning("Приложение останавливается, прерываю прогон %s", self._current_id)
        self._abort_reason = f"Прогон прерван остановкой приложения. {CANCELLED_HINT}"
        self._terminate()

        if self._thread is not None:
            self._thread.join(timeout=KILL_GRACE * 2)

    @property
    def current_id(self) -> int | None:
        return self._current_id

    def secret(self, run_id: int) -> str:
        """Пароль панели этого прогона, пока он жив в памяти процесса."""
        return self._secrets.get(run_id, "")

    # ------------------------------------------------------------------ #
    # Запуск
    # ------------------------------------------------------------------ #

    def launch(self, db: Session, data: ProvisionIn) -> ProvisionRun:
        """Проверяет ввод, создаёт строку прогона и запускает плейбук."""
        available, reason = provision.availability()

        if not available:
            raise HTTPException(status_code=400, detail=reason)

        provision.validate(data)

        with self._guard:
            if self._current_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Уже идёт прогон (#{self._current_id}) — дождитесь или прервите его",
                )

            run = provision.create_run(db, data)
            self._current_id = run.id
            self._abort_reason = ""

        try:
            prepared = provision.prepare(run, data)
        except OSError as exc:
            detail = f"Не удалось подготовить прогон: {exc}"
            self._finish(run.id, ProvisionStatus.FAILED, detail)
            self._release()
            raise HTTPException(status_code=500, detail=detail) from exc

        self._secrets = {run.id: prepared.password}

        self._thread = threading.Thread(
            target=self._run,
            args=(run.id, data, prepared),
            daemon=True,
        )
        self._thread.start()

        return run

    def cancel(self, run_id: int) -> None:
        """Прерывает прогон. Сервер может остаться недонастроенным — кнопка аварийная."""
        if self._current_id != run_id:
            raise HTTPException(status_code=400, detail="Этот прогон уже не идёт")

        self._abort_reason = f"Прогон прерван. {CANCELLED_HINT}"
        self._terminate()

    # ------------------------------------------------------------------ #
    # Подпроцесс
    # ------------------------------------------------------------------ #

    def _environment(self) -> dict[str, str]:
        """Окружение плейбука.

        Цвет выключаем — иначе лог приезжает на страницу в ANSI-кодах. `known_hosts`
        свой: `~/.ssh` смонтирован только на чтение, а ssh при первом заходе хочет
        дописать туда ключ нового сервера. Заодно переустановленный сервер со
        сменившимся ключом не упирается в запись из прошлой жизни.
        """
        known_hosts = provision.base_dir() / "known_hosts"

        return os.environ | {
            "ANSIBLE_CONFIG": str(provision.ansible_dir() / "ansible.cfg"),
            "ANSIBLE_NOCOLOR": "1",
            "ANSIBLE_FORCE_COLOR": "0",
            # Добавляется к ssh_args из ansible.cfg, а не заменяет их. Путь в кавычках:
            # ansible режет эту строку по пробелам, а каталог проекта вполне может их
            # содержать — без кавычек ssh принимает хвост пути за имя хоста.
            "ANSIBLE_SSH_EXTRA_ARGS": f"-o UserKnownHostsFile={shlex.quote(str(known_hosts))}",
            "PYTHONUNBUFFERED": "1",
        }

    def _terminate(self) -> None:
        """Убивает группу процессов плейбука: у него есть дети — ssh и sshpass."""
        process = self._process

        if process is None or process.poll() is not None:
            return

        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError) as exc:
            log.warning("Не удалось прервать плейбук: %s", exc)
            return

        try:
            process.wait(timeout=KILL_GRACE)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)

    def _run(self, run_id: int, data: ProvisionIn, prepared: PreparedRun) -> None:
        """Тело потока: гонит плейбук, пишет лог, закрывает строку прогона."""
        status = ProvisionStatus.FAILED
        error: str | None = None
        registered = False

        try:
            code = self._spawn(run_id, prepared)

            if self._abort_reason:
                status = ProvisionStatus.CANCELLED
                error = self._abort_reason
            elif code == 0:
                status = ProvisionStatus.DONE
                registered, error = self._register(data, prepared)
            else:
                error = provision.log_tail(run_id) or f"ansible-playbook вышел с кодом {code}"

        except Exception as exc:  # поток не должен падать молча
            log.exception("Прогон %s сорвался", run_id)
            error = f"Прогон сорвался: {exc}"

        finally:
            provision.cleanup(run_id)
            self._finish(run_id, status, error, registered=registered)
            self._release()

    def _release(self) -> None:
        with self._guard:
            self._current_id = None
            self._process = None

    def _spawn(self, run_id: int, prepared: PreparedRun) -> int:
        """Запускает плейбук и читает его вывод до конца."""
        command = [
            "ansible-playbook",
            provision.playbook().name,
            "-i",
            str(prepared.inventory),
            # Файлом, а не строкой: аргументы процесса видны в `ps`, а внутри пароли.
            "-e",
            f"@{prepared.variables}",
        ]

        log.info("Прогон %s: %s", run_id, " ".join(command))

        process = subprocess.Popen(  # команда собрана здесь, извне не приходит
            command,
            cwd=provision.ansible_dir(),
            env=self._environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            # Своя группа процессов: прервать надо и ssh с sshpass, а не только питон.
            start_new_session=True,
        )

        with self._guard:
            self._process = process

        self._arm_timeout(run_id)

        try:
            self._consume(run_id, process)
            return process.wait()
        finally:
            self._disarm_timeout()

    def _arm_timeout(self, run_id: int) -> None:
        """Будильник на случай зависшего плейбука."""
        minutes = max(get_settings().PROVISION_TIMEOUT_MIN, 1)

        def fire() -> None:
            log.warning("Прогон %s идёт дольше %d минут, прерываю", run_id, minutes)
            self._abort_reason = f"Прогон шёл дольше {minutes} минут и прерван. {CANCELLED_HINT}"
            self._terminate()

        self._timer = threading.Timer(minutes * 60, fire)
        self._timer.daemon = True
        self._timer.start()

    def _disarm_timeout(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _consume(self, run_id: int, process: subprocess.Popen[str]) -> None:
        """Переливает вывод плейбука в лог, попутно обновляя шаг и итог прогона."""
        if process.stdout is None:
            return

        recap_ahead = False
        log_file = provision.log_path(run_id).open("a", encoding="utf-8")

        with SessionLocal() as db, log_file:
            for raw in process.stdout:
                log_file.write(raw)
                log_file.flush()

                line = raw.strip()

                if line.startswith(("TASK [", "PLAY [")):
                    self._set(db, run_id, step=_inside_brackets(line))
                elif line.startswith("PLAY RECAP"):
                    recap_ahead = True
                elif recap_ahead and line:
                    # Хост у нас один, поэтому первая строка после RECAP — его итог.
                    self._set(db, run_id, recap=line[:512])
                    recap_ahead = False

    # ------------------------------------------------------------------ #
    # База
    # ------------------------------------------------------------------ #

    def _register(self, data: ProvisionIn, prepared: PreparedRun) -> tuple[bool, str | None]:
        """Дописывает сервер в `servers.yml` и просит воркер забыть старые соединения."""
        try:
            provision.register(data, prepared.password, prepared.web_path)
        except Exception as exc:  # сервер уже поднят, об этом надо сказать
            log.exception("Сервер %s поднят, но в servers.yml не дописан", data.key)
            detail = getattr(exc, "detail", None) or str(exc)

            return False, (
                f"Сервер поднят, но в servers.yml не дописан: {detail}. "
                "Добавьте его кнопкой «Подключить готовый»."
            )

        self._config_worker.forget_panels()

        return True, None

    @staticmethod
    def _set(db: Session, run_id: int, **values) -> None:
        db.query(ProvisionRun).filter_by(id=run_id).update(values)
        db.commit()

    def _finish(
        self,
        run_id: int,
        status: ProvisionStatus,
        error: str | None,
        *,
        registered: bool = False,
    ) -> None:
        with SessionLocal() as db:
            self._set(
                db,
                run_id,
                status=status,
                error=error,
                registered=registered,
                finished_at=_now(),
            )


def _inside_brackets(line: str) -> str:
    """`TASK [docker : Install Docker] ****` → `docker : Install Docker`."""
    start = line.find("[")
    end = line.rfind("]")

    if start == -1 or end <= start:
        return line

    return line[start + 1 : end]
