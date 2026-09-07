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

from app.core.servers import ArtifactKind, PanelKind
from app.services import server_service as srv

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.db.models import Campaign, Config, Recipient

log = logging.getLogger("vibe_mail.mail_sender")

# Заголовок блока со ссылками подписки в конце письма.
LINKS_HEADER = "Ссылки подписки:"

# Памятка получателю. Собирается по тому, что человеку реально досталось: писать про
# файлы тому, кому уехали одни ссылки, — значит заставить его гадать, что он потерял.
HOWTO_HEADER = "Чем открыть:"

# Клиенты для ссылки подписки (VLESS/Reality). Ссылки проверены: у happ обязателен
# www, без него домен переехал и отдаёт 404. Для FoXray ссылки нет намеренно —
# страницы, выдающие себя за официальные, ведут на TestFlight и выглядят подделкой,
# а посылать тридцати людям сомнительную ссылку хуже, чем попросить найти по названию.
# Порядок не случайный: сначала то, что ставится без чужого аккаунта App Store.
LINK_CLIENTS = (
    "Ссылку подписки можно открыть прямо в браузере — там список подходящих "
    "приложений и QR-коды, с телефона проще всего отсканировать. Можно и наоборот: "
    "скопировать ссылку и добавить её в приложение вручную, кнопкой «Добавить "
    "подписку» или «Add subscription». Дальше приложение само скачает настройки и "
    "будет обновлять их без вашего участия.\n"
    "\n"
    "Подойдёт любое из:\n"
    "  Happ — https://www.happ.su/main/ru\n"
    "  Incy (iPhone, Android, компьютер) — https://incy.cc/\n"
    "  Husi (Android) — https://github.com/xchacha20-poly1305/husi\n"
    "  Streisand (iPhone, iPad, Mac) — https://apps.apple.com/app/id6450534064\n"
    "  FoXray (iPhone, iPad, Mac) — найдите по названию в App Store\n"
    "\n"
    "Streisand и FoXray из российского App Store, скорее всего, не поставятся — "
    "для них нужен аккаунт другой страны. Первые три доступны без этого.\n"
    "\n"
    "Если вы пользовались NekoBox на Android — стоит перейти на любое из "
    "перечисленных: NekoBox больше не развивают, и работает он всё хуже."
)

# Клиенты для файла .conf, по типу панели. AmneziaWG — отдельная строка не для
# красоты: её конфиг содержит параметры обфускации, и обычный WireGuard такой файл
# не откроет.
FILE_CLIENTS: dict[PanelKind, str] = {
    PanelKind.AMNEZIA: (
        "открываются приложением Amnezia (https://amnezia.org/), а на Android ещё и "
        "WG Tunnel (https://www.wgtunnel.com/). Обычный WireGuard их не примет: "
        "внутри настройки маскировки, которых он не знает."
    ),
    PanelKind.WG_EASY: (
        "открываются официальным WireGuard (https://www.wireguard.com/install/), "
        "WG Tunnel (https://www.wgtunnel.com/) или Amnezia (https://amnezia.org/) — "
        "подойдёт любое."
    ),
}


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

    @staticmethod
    def _panel_kind(server_key: str) -> PanelKind | None:
        """Тип панели сервера; None — сервера уже нет в конфиге."""
        server = srv.find_server(server_key)
        return server.panel if server else None

    def _howto_block(self, configs: list[Config]) -> str:
        """Памятка «чем открыть». Пустая строка, если сказать нечего.

        Строки собираются по тому, что человеку досталось: получателю с одними
        ссылками не нужен абзац про вложения, а владельцу файла с AmneziaWG важно
        знать, что обычный WireGuard его не откроет.
        """
        lines = []

        if any(c.kind is ArtifactKind.LINK and c.link for c in configs):
            lines.append(LINK_CLIENTS)

        files = [c for c in configs if c.kind is ArtifactKind.FILE and c.content is not None]
        seen: set[PanelKind] = set()

        for config in files:
            kind = self._panel_kind(config.server_key)
            advice = FILE_CLIENTS.get(kind) if kind else None

            if advice is None or kind in seen:
                continue

            seen.add(kind)
            # Приписываем окончание имени файла: у человека во вложениях несколько
            # .conf, и без этого непонятно, к какому из них абзац.
            lines.append(
                f"{self._server_title(config.server_key)}, "
                f"файлы …_{config.server_key}.conf — {advice}"
            )

        if not lines:
            return ""

        return "\n\n".join(["", HOWTO_HEADER, "\n\n".join(lines)])

    def _compose_body(self, campaign: Campaign, configs: list[Config]) -> str:
        """Текст письма: тело кампании, ссылки подписки, следом памятка."""
        return f"{campaign.body}{self._links_block(configs)}{self._howto_block(configs)}"

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
