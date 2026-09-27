"""Доступ к списку VPN-серверов и правка этого списка из интерфейса.

Список живёт в `servers.yml` (путь в настройках) и кешируется на процесс. Здесь —
чтение с переводом «сервера с таким ключом нет» в честный 404, наборы серверов для
операций и три правки файла: включить, добавить, удалить. Сама запись — в
`core.servers_file`, чтобы место правки файла было одно.

Отдельно живёт проба панели (`probe_server`): то же соединение, что поднимает
генерация, но без создания клиента. Ею пользуются и кнопка в интерфейсе, и
`check_servers.py` — иначе диагностика разошлась бы в двух местах.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func

from app.core import servers_file
from app.core.config import get_settings
from app.core.constants import SERVER_KEY_RE
from app.core.servers import ServerConfig, TransportKind, get_servers, reload_servers
from app.core.servers_file import ServersFileError
from app.db.models import Campaign, Config, ConfigStatus
from app.schemas.server import ServerCheck, ServerCreate, ServerRead
from app.services.panels import PanelError, build_panel
from app.services.panels.amnezia import AmneziaPanel
from app.services.panels.xui import XuiPanel

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

log = logging.getLogger("vibe_mail.server_service")

# Сколько имён клиентов возвращает проба: достаточно, чтобы узнать панель в лицо, и
# мало, чтобы не превращать ответ в простыню.
SAMPLE_CLIENTS = 10


def all_servers() -> list[ServerConfig]:
    """Все серверы из конфига, включая выключенные."""
    return get_servers(get_settings().VPN_SERVERS_FILE).servers


def enabled_servers() -> list[ServerConfig]:
    """Серверы, включённые в рассылки по умолчанию."""
    return get_servers(get_settings().VPN_SERVERS_FILE).enabled


def enabled_keys() -> list[str]:
    return [server.key for server in enabled_servers()]


def find_server(key: str) -> ServerConfig | None:
    """Сервер по ключу либо None. Для фонового кода, которому HTTP-исключения ни к чему."""
    return next((server for server in all_servers() if server.key == key), None)


def get_server(key: str) -> ServerConfig:
    """Сервер по ключу; 404, если такого в конфиге нет."""
    server = find_server(key)
    if server is None:
        raise HTTPException(status_code=404, detail=f"Сервер {key} не найден в конфиге")
    return server


def get_enabled_server(key: str) -> ServerConfig:
    """То же, но выключенный сервер отвергается.

    Нужно там, где действие создаёт конфиги: генерация выключенные серверы не берёт,
    и привязка к такому серверу оставила бы строку, которую нечем наполнить.
    """
    server = get_server(key)

    if not server.enabled:
        raise HTTPException(
            status_code=400,
            detail=f"Сервер {key} выключен — конфиги на нём не заводятся",
        )

    return server


def servers_by_keys(keys: list[str]) -> list[ServerConfig]:
    """Включённые серверы из набора, в порядке конфига."""
    chosen = set(keys)
    return [server for server in enabled_servers() if server.key in chosen]


def campaign_keys(chosen: list[str] | None) -> list[str]:
    """Серверы рассылки: сохранённый у неё выбор либо все включённые.

    Пусто (в том числе `NULL` у кампаний, созданных до появления выбора) — значит все
    включённые. Выключенные из выбора выпадают: конфиги на них всё равно не завести, а
    молча заводить строку, которую нечем наполнить, хуже, чем её не заводить.
    """
    if not chosen:
        return enabled_keys()

    enabled = set(enabled_keys())
    return [key for key in chosen if key in enabled]


def keys_for_campaign(db: Session, campaign_id: int) -> list[str]:
    """Серверы рассылки по её id — то же, что `campaign_keys`, но читает набор из базы.

    Берём одну колонку, а не кампанию целиком: это нужно и разбору импорта, которому
    ORM-объект кампании ни к чему.
    """
    chosen = db.query(Campaign.servers).filter_by(id=campaign_id).scalar()

    return campaign_keys(chosen)


def resolve_keys(keys: list[str] | None, allowed: list[str] | None = None) -> list[str]:
    """Ключи серверов для операции: пустой список или None — значит все допустимые.

    `allowed` — из чего выбирать; по умолчанию все включённые серверы, а для операции
    внутри рассылки — её набор. Явно перечисленные проверяются: опечатка в ключе не
    должна тихо превращаться в «ничего не сделали».
    """
    permitted = enabled_keys() if allowed is None else allowed

    if not keys:
        return permitted

    unknown = [key for key in keys if key not in permitted]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестные, выключенные или не входящие в рассылку серверы: "
            f"{', '.join(unknown)}",
        )

    return keys


# ---------------------------------------------------------------------- #
# Чтение для интерфейса
# ---------------------------------------------------------------------- #


def describe_where(server: ServerConfig) -> str:
    """Куда и чем ходим за конфигами: через SSH или напрямую."""
    if server.ssh is not None:
        return f"ssh {server.ssh.host} → {server.base_url}"
    return server.base_url


def configs_by_server(db: Session) -> dict[str, tuple[int, int]]:
    """Ключ сервера → (сколько строк конфигов, сколько из них без артефакта).

    Первое число нужно удалению сервера (его строки останутся в прошлых рассылках),
    второе — выключению: незаполненные конфиги не дадут запустить рассылку.
    """
    rows = (
        db.query(Config.server_key, Config.status, func.count(Config.id))
        .group_by(Config.server_key, Config.status)
        .all()
    )

    totals: dict[str, tuple[int, int]] = {}

    for server_key, status, count in rows:
        total, unfinished = totals.get(server_key, (0, 0))
        totals[server_key] = (
            total + count,
            unfinished + (count if status is not ConfigStatus.READY else 0),
        )

    return totals


def read_servers(db: Session) -> list[ServerRead]:
    """Список серверов для интерфейса — вместе со счётчиками конфигов."""
    counts = configs_by_server(db)

    return [_read(server, counts.get(server.key, (0, 0))) for server in all_servers()]


def _read(server: ServerConfig, counts: tuple[int, int]) -> ServerRead:
    total, unfinished = counts

    return ServerRead(
        key=server.key,
        title=server.title,
        panel=server.panel,
        transport=server.transport,
        artifact=server.artifact_kind,
        enabled=server.enabled,
        where=describe_where(server),
        configs=total,
        unfinished=unfinished,
    )


# ---------------------------------------------------------------------- #
# Правка servers.yml
# ---------------------------------------------------------------------- #


def add_server(data: ServerCreate) -> ServerRead:
    """Дописывает сервер в конфиг. Ключ проверяется отдельно от остальных полей.

    Ключ лежит в БД у каждого конфига и уезжает в имена вложений, поэтому набор символов
    ограничен, а занятый ключ отвергается: молча слиться с существующим сервером — это
    чужие конфиги под своим именем.
    """
    if not SERVER_KEY_RE.match(data.key):
        raise HTTPException(
            status_code=400,
            detail="Ключ сервера: строчные латинские буквы, цифры, дефис и подчёркивание",
        )

    if find_server(data.key) is not None:
        raise HTTPException(status_code=400, detail=f"Сервер с ключом {data.key} уже есть")

    payload = data.model_dump(mode="json", exclude_defaults=True)
    _edit_file(lambda path: servers_file.append_server(path, payload))

    # Читаем то, что легло в файл, а не то, что пришло в запросе: так в ответ попадает
    # ровно то, с чем дальше будет работать приложение.
    return _read(get_server(data.key), (0, 0))


def set_server_enabled(db: Session, key: str, enabled: bool) -> ServerRead:
    """Включает сервер в рассылки по умолчанию или исключает из них.

    Уже заведённые строки конфигов не трогаются: выключение говорит только о том, что
    новых на этом сервере не появится.
    """
    get_server(key)
    _edit_file(lambda path: servers_file.set_enabled(path, key, enabled))

    return _read(get_server(key), configs_by_server(db).get(key, (0, 0)))


def remove_server(db: Session, key: str, force: bool = False) -> int:
    """Убирает сервер из конфига. Возвращает число оставшихся на него ссылок.

    Строки конфигов в прошлых рассылках не удаляются — это история того, что людям уже
    ушло. Но ссылаться они будут на сервер, которого в конфиге нет, поэтому без явного
    `force` такое удаление отвергается с числом строк.

    Клиентов на самой панели не касаемся: удалить сервер из списка — не то же самое, что
    отобрать у людей доступ.
    """
    get_server(key)
    total, _ = configs_by_server(db).get(key, (0, 0))

    if total and not force:
        raise HTTPException(
            status_code=400,
            detail=f"На сервер {key} ссылаются конфиги в рассылках: {total}. "
            "Удалить можно, но эти строки останутся без сервера.",
        )

    _edit_file(lambda path: servers_file.remove_server(path, key))

    return total


def _edit_file(edit: Callable[[str], None]) -> None:
    """Правит `servers.yml` и сбрасывает кеш списка.

    Сломанную правку файл откатывает сам (`core.servers_file`), сюда она приезжает
    исключением — отвечаем 500 с его текстом: он объясняет, что случилось с файлом.
    """
    path = get_settings().VPN_SERVERS_FILE

    try:
        edit(path)
    except ServersFileError as exc:
        log.exception("Не удалось записать %s", path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    reload_servers()


# ---------------------------------------------------------------------- #
# Панели
# ---------------------------------------------------------------------- #


def probe_server(server: ServerConfig, name: str = "") -> ServerCheck:
    """Проверяет всё, что нужно генерации, кроме создания клиента.

    Создание не трогаем намеренно: лишний клиент на боевой панели потом придётся
    удалять руками. Ошибку не поднимаем, а возвращаем в результате — проверка на то и
    нужна, чтобы её показать, а не чтобы упасть.
    """
    started = time.monotonic()
    result = ServerCheck(key=server.key, ok=False)
    panel = build_panel(server)

    try:
        names = sorted(panel.list_client_names())
        result.clients = len(names)
        result.sample = names[:SAMPLE_CLIENTS]

        if isinstance(panel, XuiPanel):
            # Приватный метод дёргаем осознанно: наружу его выставлять незачем, а
            # проверить надо именно его — на нём ломается ссылка, если панель за прокси.
            result.subscription = panel._subscription_base()

        if isinstance(panel, AmneziaPanel):
            result.protocol = panel.protocol()

        if name:
            result.client_found = bool(panel.fetch_client(name))

        result.ok = True

    except Exception as exc:  # noqa: BLE001 - смысл пробы в том, чтобы показать ошибку
        result.error = str(exc)
        result.hint = setup_hint(server, result.error)

    finally:
        panel.close()
        result.elapsed_ms = int((time.monotonic() - started) * 1000)

    return result


def check_server(key: str, name: str = "") -> ServerCheck:
    """Проба сервера по ключу — для ручки API."""
    return probe_server(get_server(key), name)


# Две ошибки, на которые напарываются при первой настройке: в base_url попадает
# локальный порт проброса вместо серверного, и не снят verify_tls у панели с
# сертификатом на домен. По тексту ошибки видно, которая из них.
def setup_hint(server: ServerConfig, error: str) -> str:
    """Подсказка к типовой ошибке настройки; пусто — совет не нашёлся."""
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

    return ""


def list_panel_clients(key: str) -> list[str]:
    """Имена клиентов, которые сейчас есть на панели этого сервера.

    Нужно интерфейсу привязки: клиентов, заведённых руками, надо показать человеку,
    чтобы он сопоставил их с получателями. Соединение здесь одноразовое — это редкое
    действие из интерфейса, а не горячий путь генерации.
    """
    server = get_server(key)
    panel = build_panel(server)

    try:
        return sorted(panel.list_client_names())
    except PanelError as exc:
        raise HTTPException(status_code=502, detail=f"Панель {server.title}: {exc}") from exc
    finally:
        panel.close()
