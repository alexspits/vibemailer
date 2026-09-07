"""Проверка связи с VPN-панелями. Ничего на них не меняет.

Нужен перед первым боевым прогоном: генерация ходит на панели из фонового воркера,
и разбираться там, почему не подключилось, неудобно — ошибка видна только в статусе
конфига. Здесь то же самое соединение поднимается вручную и с объяснением.

    pipenv run python check_servers.py            # все включённые серверы
    pipenv run python check_servers.py ru de2      # только эти
    pipenv run python check_servers.py --name adonm  # ещё и поискать клиента по имени
    pipenv run python check_servers.py --bindings    # сверить привязки из БД с панелями

Проверяется всё, что нужно генерации, кроме самого создания клиента: SSH или HTTP до
панели, авторизация, чтение списка клиентов, а для 3x-ui — ещё и база ссылки подписки.
Создание не трогаем намеренно: лишний клиент на боевом сервере потом придётся удалять
руками.
"""

from __future__ import annotations

import argparse
import logging
import sys
from difflib import get_close_matches

from app.core.config import get_settings
from app.core.servers import PanelKind, ServerConfig, TransportKind
from app.db.models import Config
from app.db.session import SessionLocal
from app.services import server_service as srv
from app.services.panels import build_panel
from app.services.panels.xui import XuiPanel

# Сколько имён клиентов показывать, чтобы вывод не превращался в простыню.
SAMPLE = 10


def _servers(keys: list[str]) -> list[ServerConfig]:
    """Серверы для проверки: перечисленные либо все включённые."""
    if not keys:
        return srv.enabled_servers()

    chosen = []
    for key in keys:
        server = srv.find_server(key)
        if server is None:
            sys.exit(f"Сервера {key} нет в {get_settings().VPN_SERVERS_FILE}")
        chosen.append(server)

    return chosen


def _describe(server: ServerConfig) -> str:
    """Строка заголовка: куда и чем идём."""
    where = f"ssh {server.ssh.host} → {server.base_url}" if server.ssh else server.base_url
    return f"[{server.key}] {server.title} — {server.panel}, {where}"


def _report_subscription(panel: XuiPanel) -> None:
    """База ссылки подписки — единственное, что 3x-ui берёт из настроек панели."""
    # Приватный метод дёргаем осознанно: наружу его выставлять незачем, а проверить
    # надо именно его — на нём ломается ссылка, если панель стоит за прокси.
    base = panel._subscription_base()
    print(f"  подписка: {base}<имя конфига>")


# Две ошибки, на которые напарываются при первой настройке: в base_url попадает
# локальный порт проброса вместо серверного, и не снят verify_tls у панели с
# сертификатом на домен. По тексту ошибки видно, которая из них.
def _hint(server: ServerConfig, error: str) -> str | None:
    """Подсказка к типовой ошибке настройки; None — совет не нашёлся."""
    if any(sign in error for sign in ("кодом 7", "Connection refused", "onnect to server")):
        if server.transport is TransportKind.SSH:
            return (
                "порт в base_url должен быть тем, что панель слушает на сервере. "
                "Локальный порт из LocalForward в ~/.ssh/config не подойдёт: "
                "проброс не нужен, curl запускается на самом сервере."
            )
        return "панель не отвечает по этому адресу — проверьте хост и порт."

    if "certificate" in error or "CERTIFICATE" in error or "кодом 60" in error:
        return (
            "сертификат выписан на другое имя. Если это самоподписанный сертификат "
            "панели — verify_tls: false. Если имя чужое, вы скорее всего попали не на "
            "ту панель: проверьте порт в base_url."
        )

    return None


def _check(server: ServerConfig, name: str) -> bool:
    """Одна панель: список клиентов и, если просили, поиск имени. True — всё вышло."""
    print(_describe(server))
    panel = build_panel(server)

    try:
        names = sorted(panel.list_client_names())
        print(f"  клиентов на панели: {len(names)}")

        if names:
            shown = ", ".join(names[:SAMPLE])
            tail = f" … и ещё {len(names) - SAMPLE}" if len(names) > SAMPLE else ""
            print(f"  например: {shown}{tail}")

        if isinstance(panel, XuiPanel):
            _report_subscription(panel)

        if name:
            found = panel.fetch_client(name)
            print(f"  клиент {name}: {'нашёлся' if found else 'на панели нет'}")

    except Exception as exc:  # noqa: BLE001 - смысл скрипта в том, чтобы показать ошибку
        print(f"  ОШИБКА: {exc}")
        advice = _hint(server, str(exc))
        if advice:
            print(f"  ПОДСКАЗКА: {advice}")
        return False

    else:
        return True

    finally:
        panel.close()


# Привязка — это обещание «такой клиент на панели уже есть». Обещание легко нарушить
# опечаткой: в панели `LitovkaP1`, в импорте `litovkap`. Генерация на этом честно
# падает, но узнать об этом лучше до прогона, а не по десятку FAILED.
def _suggest(name: str, live: set[str]) -> list[str]:
    """Похожие имена с панели: сначала совпадение по началу, потом близкие по буквам."""
    lowered = name.lower()
    prefixed = sorted(n for n in live if n.lower().startswith(lowered))

    return prefixed[:3] or get_close_matches(name, sorted(live), n=3, cutoff=0.7)


def _check_bindings(keys: list[str]) -> int:
    """Сверяет `external_name` всех конфигов с живыми панелями. Возвращает код возврата."""
    db = SessionLocal()
    try:
        bound = db.query(Config).filter(Config.external_name.isnot(None)).all()
        wanted = {c.server_key for c in bound}
        if keys:
            wanted &= set(keys)

        if not bound:
            print("Привязок в базе нет — сверять нечего.")
            return 0

        broken = 0
        for key in sorted(wanted):
            panel = build_panel(srv.get_server(key))
            try:
                live = set(panel.list_client_names())
            except Exception as exc:  # noqa: BLE001 - смысл скрипта в том, чтобы показать ошибку
                print(f"[{key}] ОШИБКА: {exc}")
                broken += 1
                continue
            finally:
                panel.close()

            mine = [c for c in bound if c.server_key == key]
            missing = [c for c in mine if c.external_name not in live]
            print(f"[{key}] привязок {len(mine)}, не найдено на панели: {len(missing)}")

            for config in missing:
                hints = _suggest(config.external_name or "", live)
                tail = f" — похоже на {', '.join(hints)}" if hints else " — похожих имён нет"
                print(f"  {config.external_name!r} у «{config.recipient.email}»{tail}")

            broken += len(missing)

        print()
        if broken:
            print(f"Привязок под вопросом: {broken}. Генерация по ним не пойдёт.")
            return 1

        print("Все привязки нашлись на панелях.")
        return 0

    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("keys", nargs="*", help="ключи серверов; без них — все включённые")
    parser.add_argument("--name", default="", help="проверить, есть ли на панели такой клиент")
    parser.add_argument(
        "--bindings",
        action="store_true",
        help="сверить привязки из БД с именами на панелях",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="показать лог запросов")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # httpcore на DEBUG печатает заголовки ответа целиком, включая Set-Cookie с
    # сессией панели. Свой лог видеть хочется, чужой — нет: вывод `-v` попадает
    # в переписку и баг-репорты.
    for noisy in ("httpcore", "httpx", "paramiko"):
        logging.getLogger(noisy).setLevel(logging.INFO)

    if args.bindings:
        return _check_bindings(args.keys)

    servers = _servers(args.keys)

    if not servers:
        sys.exit(f"В {get_settings().VPN_SERVERS_FILE} нет включённых серверов")

    fakes = [s.key for s in servers if s.panel is PanelKind.FAKE]
    if fakes:
        print(f"ВНИМАНИЕ: заглушки, а не боевые панели: {', '.join(fakes)}\n")

    failed = [server.key for server in servers if not _check(server, args.name)]
    print()

    if failed:
        print(f"Не отвечают: {', '.join(failed)}")
        return 1

    print(f"Все панели отвечают: {len(servers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
