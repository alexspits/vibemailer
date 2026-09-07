"""Отправка писем через SMTP.

Инкапсулирует всю работу с smtplib: подключение (SSL/STARTTLS), сборку
письма, ретраи с переподключением. Не ходит в базу — получает готовые объекты
кампании, получателя и его конфигов с уже загруженным содержимым файлов.

У получателя конфиги с нескольких серверов и двух разных видов: файлы `.conf`
уезжают вложениями, а ссылки подписки вложением быть не могут — они дописываются
в конец тела письма, каждая со своим сервером, чтобы человек понимал, что к чему.
"""

from __future__ import annotations

import contextlib
import logging
import smtplib
import ssl
import time
from collections import Counter
from email.message import EmailMessage
from email.utils import formataddr
from typing import TYPE_CHECKING

from app.core.servers import ArtifactKind
from app.services import server_service as srv

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.db.models import Campaign, Config, Recipient

log = logging.getLogger("vibe_mail.mail_sender")

# Заголовок блока со ссылками подписки в конце письма.
LINKS_HEADER = "Ссылки подписки:"


class MailSender:
    """Класс-интерфейс отправки писем одному получателю."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------------ #
    # Внутреннее: подключение и сборка письма
    # ------------------------------------------------------------------ #

    def _connect(self) -> smtplib.SMTP | smtplib.SMTP_SSL:
        """Устанавливает соединение с SMTP и логинится."""
        host = self.settings.SMTP_HOST
        port = int(self.settings.SMTP_PORT)
        context = ssl.create_default_context()
        use_ssl = self.settings.SMTP_USE_SSL or port == 465

        if use_ssl:
            smtp = smtplib.SMTP_SSL(host, port, context=context, timeout=30)
        else:
            smtp = smtplib.SMTP(host, port, timeout=30)
            smtp.ehlo()
            if self.settings.SMTP_USE_TLS:
                smtp.starttls(context=context)
                smtp.ehlo()

        smtp.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD)
        log.info("Подключено к %s:%s как %s", host, port, self.settings.SMTP_USER)
        return smtp

    @staticmethod
    def _format_to(recipient: Recipient) -> str:
        """Заголовок To: с именем, если оно есть, иначе голый адрес."""
        if not recipient.name:
            return recipient.email
        return formataddr((recipient.name, recipient.email))

    @staticmethod
    def _attach_config(msg: EmailMessage, config: Config) -> None:
        """Кладёт файл конфига вложением.

        Тип всегда `application/octet-stream`, хотя по имени угадался бы `text/plain`:
        на `text/plain` Gmail в Android дописывает к файлу расширение под тип, и
        `alice-1_ru.conf` сохраняется как `alice-1_ru.conf.txt` — импорт в WireGuard
        такой файл уже не берёт. Тот же тип отдаёт и наша кнопка скачивания.
        """
        msg.add_attachment(
            config.content,
            maintype="application",
            subtype="octet-stream",
            filename=config.download_filename,
        )

    @staticmethod
    def _server_title(server_key: str) -> str:
        """Название сервера для человека; если сервера уже нет в конфиге — его ключ."""
        server = srv.find_server(server_key)
        return server.title if server else server_key

    def _links_block(self, configs: list[Config]) -> str:
        """Блок со ссылками подписки. Пустая строка, если ссылок нет.

        Подписываем сервером и порядковым номером, а не именем конфига: `ivan-i-2`
        человеку ничего не говорит, а «Германия (3x-ui) 2» отвечает ровно на его вопрос,
        какая ссылка какая. Номер появляется, только когда ссылок на сервер больше одной.

        Латиница остаётся в именах файлов: там она не подпись для человека, а имя, под
        которым файл ляжет на диск, и различать вложения нужно именно им.
        """
        linked = [config for config in configs if config.kind is ArtifactKind.LINK and config.link]
        per_server = Counter(config.server_key for config in linked)
        seen: Counter[str] = Counter()
        lines = []

        for config in linked:
            seen[config.server_key] += 1
            title = self._server_title(config.server_key)
            number = f" {seen[config.server_key]}" if per_server[config.server_key] > 1 else ""
            lines.append(f"{title}{number}: {config.link}")

        if not lines:
            return ""

        return "\n\n".join(["", LINKS_HEADER, "\n".join(lines)])

    def _compose_body(self, campaign: Campaign, configs: list[Config]) -> str:
        """Текст письма: тело кампании, следом ссылки подписки."""
        return f"{campaign.body}{self._links_block(configs)}"

    def _build_message(
        self, campaign: Campaign, recipient: Recipient, configs: list[Config]
    ) -> EmailMessage:
        """Собирает EmailMessage: текст кампании со ссылками и файлы конфигов вложениями."""
        msg = EmailMessage()
        msg["From"] = self.settings.SMTP_USER
        msg["To"] = self._format_to(recipient)
        msg["Subject"] = campaign.subject
        # quoted-printable, а не подобранный по умолчанию base64: у письма с вложениями
        # тело в base64 замораживается с переводами строк `\n`, а почта требует `\r\n`.
        # Клиенты на таком теле склеивают соседние строки — ссылка уезжала вместе с
        # именем следующей.
        msg.set_content(self._compose_body(campaign, configs), cte="quoted-printable")

        for config in configs:
            # Конфиг без файла пропускаем: до отправки такой кампании дело не дойдёт,
            # её не пропустит validate_campaign_ready.
            if config.kind is ArtifactKind.FILE and config.content is not None:
                self._attach_config(msg, config)

        return msg

    @staticmethod
    def _is_temporary(exc: Exception) -> bool:
        """Временная ли ошибка (стоит повторить) или постоянная."""
        if isinstance(exc, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError)):
            return True
        if isinstance(exc, smtplib.SMTPResponseException):
            return 400 <= exc.smtp_code < 500
        return isinstance(exc, (TimeoutError, ConnectionError, OSError))

    # ------------------------------------------------------------------ #
    # Публичное API
    # ------------------------------------------------------------------ #

    def _send_once(self, msg: EmailMessage) -> None:
        """Одна попытка отправки: соединение, письмо, гарантированное закрытие."""
        smtp = None
        try:
            smtp = self._connect()
            smtp.send_message(msg)
        finally:
            if smtp is not None:
                with contextlib.suppress(Exception):
                    smtp.quit()

    def _wait_before_retry(self, exc: Exception, attempt: int) -> None:
        """Экспоненциальная пауза между попытками: 2, 4, 8 секунд."""
        delay = 2**attempt
        log.warning(
            "Временная ошибка (%s), попытка %d/%d, пауза %d с",
            exc,
            attempt,
            self.settings.RETRIES,
            delay,
        )
        time.sleep(delay)

    def send(
        self, campaign: Campaign, recipient: Recipient, configs: list[Config]
    ) -> tuple[bool, str | None]:
        """Отправляет письмо с ретрами.

        Возвращает (успех, текст_ошибки). При постоянной ошибке (5xx, отказ
        получателя/отправителя) возвращает неуспех сразу, без повторов.
        """
        msg = self._build_message(campaign, recipient, configs)
        last_exc: Exception | None = None

        for attempt in range(1, self.settings.RETRIES + 1):
            try:
                self._send_once(msg)
            except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused) as exc:
                return (False, str(exc))
            except Exception as exc:  # noqa: BLE001 - развилка по типу ниже
                last_exc = exc
                if not self._is_temporary(exc) or attempt == self.settings.RETRIES:
                    return (False, str(exc))
                self._wait_before_retry(exc, attempt)
            else:
                return (True, None)

        return (False, str(last_exc) if last_exc else "unknown error")
