"""Проверка SMTP: подключение, шифрование, вход. Письмо шлётся только по просьбе.

Парная к check_servers.py: там панели, здесь почта. Отправка тоже идёт из фонового
воркера, где ошибка видна лишь статусом получателя, — а тут то же самое соединение
поднимается вручную и с объяснением.

    pipenv run python check_smtp.py                  # только связь и вход
    pipenv run python check_smtp.py --to я@почта.рф  # ещё и отправить себе письмо

Проверяются те же настройки, которыми пользуется рассылка (SMTP_* из .env), тем же
кодом MailSender._connect — иначе проверка проверяла бы не то, что работает потом.
"""

from __future__ import annotations

import argparse
import smtplib
import sys
from email.message import EmailMessage

from app.core.config import get_settings
from app.services.mail_sender import MailSender

# Типовые ошибки настройки: по тексту ответа сервера понятно, что именно не так.
HINTS: tuple[tuple[str, str], ...] = (
    ("authentication", "сервер не принял логин или пароль."),
    ("username and password not accepted", "нужен пароль приложения, а не основной."),
    ("starttls", "порт ждёт другого шифрования: 587 — STARTTLS, 465 — SSL."),
    ("wrong version number", "на этом порту не TLS: для 465 включите SMTP_USE_SSL."),
    ("connection refused", "на этом хосте и порту никто не слушает."),
    ("timed out", "до сервера не доехали: проверьте хост, порт и firewall."),
)


def _hint(error: str) -> str | None:
    """Подсказка по тексту ошибки; None — совет не нашёлся."""
    lowered = error.lower()
    return next((advice for sign, advice in HINTS if sign in lowered), None)


def _test_message(settings, to: str) -> EmailMessage:
    """Письмо-пустышка: важно, что оно дошло, а не что в нём написано."""
    msg = EmailMessage()
    msg["From"] = settings.SMTP_USER
    msg["To"] = to
    msg["Subject"] = "vibe_mail: проверка отправки"
    msg.set_content(
        "Это письмо отправлено скриптом check_smtp.py.\n"
        "Если оно у вас — SMTP настроен верно и рассылка сможет отправлять.\n"
    )
    return msg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", default="", help="адрес для тестового письма")
    args = parser.parse_args()

    settings = get_settings()
    mode = "SSL" if settings.SMTP_USE_SSL or settings.SMTP_PORT == 465 else "STARTTLS"
    print(f"{settings.SMTP_HOST}:{settings.SMTP_PORT} ({mode}) как {settings.SMTP_USER}")

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print("  ОШИБКА: SMTP_USER или SMTP_PASSWORD пустые — заполните .env")
        return 1

    try:
        smtp = MailSender(settings)._connect()
    except Exception as exc:  # noqa: BLE001 - смысл скрипта в том, чтобы показать ошибку
        print(f"  ОШИБКА: {exc}")
        advice = _hint(str(exc))
        if advice:
            print(f"  ПОДСКАЗКА: {advice}")
        return 1

    try:
        print("  вход выполнен")
        limit = smtp.esmtp_features.get("size")
        if limit:
            print(f"  предельный размер письма: {int(limit) // 1024} КБ")

        if args.to:
            try:
                smtp.send_message(_test_message(settings, args.to))
            except smtplib.SMTPException as exc:
                print(f"  ОШИБКА отправки: {exc}")
                return 1
            print(f"  письмо отправлено на {args.to} — проверьте ящик")
    finally:
        smtp.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
