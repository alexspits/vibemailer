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
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.servers import PanelKind, ServerConfig
from app.db.models import Config
from app.db.session import SessionLocal
from app.services import server_service as srv
from app.services.panels import build_panel
from app.services.panels.amnezia import LATEST_PROTOCOL

if TYPE_CHECKING:
    from app.schemas.server import ServerCheck


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
    return f"[{server.key}] {server.title} — {server.panel}, {srv.describe_where(server)}"


def _report_clients(result: ServerCheck) -> None:
    """Сколько клиентов на панели и несколько имён для узнавания."""
    print(f"  клиентов на панели: {result.clients}")

    if not result.sample:
        return

    hidden = (result.clients or 0) - len(result.sample)
    tail = f" … и ещё {hidden}" if hidden > 0 else ""
    print(f"  например: {', '.join(result.sample)}{tail}")


def _check(server: ServerConfig, name: str) -> bool:
    """Одна панель: печатает результат пробы. True — всё вышло.

    Сама проба живёт в `server_service.probe_server` — ею же пользуется кнопка
    «Проверить» в интерфейсе, поэтому диагностика в двух местах не расходится.
    """
    print(_describe(server))
    result = srv.probe_server(server, name)

    if not result.ok:
        print(f"  ОШИБКА: {result.error}")
        if result.hint:
            print(f"  ПОДСКАЗКА: {result.hint}")
        return False

    _report_clients(result)

    # База ссылки подписки — единственное, что 3x-ui берёт из настроек панели.
    if result.subscription:
        print(f"  подписка: {result.subscription}<имя конфига>")

    # Версия AmneziaWG задаётся при создании сервера панели и потом не меняется, а
    # клиент наследует её молча. Показываем явно: иначе «клиента завели» и «клиент
    # получил нужный протокол» — разные вещи, и расхождение всплывёт у получателя.
    if result.protocol:
        note = (
            ""
            if result.protocol == LATEST_PROTOCOL
            else f" (новее — {LATEST_PROTOCOL}, но только на новом сервере панели)"
        )
        print(f"  новые клиенты получат: {result.protocol}{note}")

    if result.client_found is not None:
        print(f"  клиент {name}: {'нашёлся' if result.client_found else 'на панели нет'}")

    return True


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

        # Считаем раздельно: смешивать «панель не ответила» с «привязка не нашлась»
        # нельзя — иначе итог «привязок под вопросом: N» врёт, когда панель недоступна
        # и её привязки просто не проверялись.
        missing_total = 0
        unreachable: list[str] = []

        for key in sorted(wanted):
            server = srv.find_server(key)

            if server is None:
                # Ключи здесь из базы: сервер могли убрать из servers.yml, оставив
                # привязки. HTTPException в CLI дала бы трейсбек вместо объяснения.
                print(f"[{key}] сервера нет в servers.yml, а привязки на него остались")
                unreachable.append(key)
                continue

            panel = build_panel(server)
            try:
                live = set(panel.list_client_names())
            except Exception as exc:  # noqa: BLE001 - смысл скрипта в том, чтобы показать ошибку
                print(f"[{key}] ОШИБКА: {exc}")
                unreachable.append(key)
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

            missing_total += len(missing)

        print()

        if unreachable:
            print(f"Не проверены (панель не ответила): {', '.join(unreachable)}")

        if missing_total:
            print(f"Привязок под вопросом: {missing_total}. Генерация по ним не пойдёт.")

        if not missing_total and not unreachable:
            print("Все привязки нашлись на панелях.")

        return 1 if (missing_total or unreachable) else 0

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
