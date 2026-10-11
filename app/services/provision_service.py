"""Поднятие нового VPN-сервера плейбуком: подготовка прогона и его следы на диске.

Сценарии лежат в самом репозитории (каталог `ansible/`) и едут в образ: одним образом
на новой машине поднимается и панель, и новые серверы. Здесь — всё, кроме самого
подпроцесса: значения для формы, проверка ввода, одноразовый inventory, файл переменных,
чтение лога и запись сервера в `servers.yml` по успеху. Подпроцесс и поток — в
`provision_runner`.

Инвентарь пользователя мы не трогаем: на каждый прогон генерируется inventory из одного
хоста. Так плейбук физически не может задеть боевые серверы, а `-l` с опечаткой — не
может превратиться в прогон по всей группе.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import secrets
import shutil
import string
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple
from urllib.parse import urlparse

import yaml
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.constants import SERVER_KEY_RE
from app.core.servers import PanelAuth, PanelKind, SshConfig, TransportKind
from app.db.models import ProvisionRun
from app.schemas.provision import (
    ProvisionDefaults,
    ProvisionIn,
    ProvisionPanel,
    ProvisionRunRead,
)
from app.schemas.server import ServerCreate
from app.services import server_service as srv

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = logging.getLogger("vibe_mail.provision")

# Имя пользователя и хоста: оба уезжают в команды плейбука, поэтому набор символов
# ограничен явно, а не «чем попало, лишь бы не пусто».
UNIX_USER_RE = re.compile(r"^[a-z_][a-z0-9_-]*$")
HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$")
# Порт для UFW: «443» либо «443/tcp».
OPEN_PORT_RE = re.compile(r"^\d{1,5}(/(tcp|udp))?$")

# Плейбук отказывается ставить панель с коротким паролем — проверяем это раньше, чтобы
# человек узнал об этом в форме, а не из лога на третьей минуте прогона.
MIN_PANEL_PASSWORD = 12
# Длина генерируемого пароля панели в байтах энтропии (token_urlsafe даёт ~1.3 символа
# на байт).
PANEL_PASSWORD_BYTES = 18
# Длина случайного webBasePath у 3x-ui — как в самом плейбуке.
WEB_PATH_LENGTH = 16

# Сколько байт лога отдаём за один запрос: страница догружает его по смещению, и
# простыня на несколько мегабайт в одном ответе ей не нужна.
LOG_CHUNK = 64 * 1024
# Сколько последних строк лога уходит в текст ошибки прогона.
ERROR_TAIL_LINES = 12


# ---------------------------------------------------------------------- #
# Доступность и значения для формы
# ---------------------------------------------------------------------- #


def ansible_dir() -> Path:
    """Каталог сценариев, абсолютным путём.

    Абсолютным обязательно: плейбук запускается с `cwd` этого каталога, и относительный
    путь к нему самому (как и к inventory с переменными) разъехался бы на второй раз.
    """
    return Path(get_settings().ANSIBLE_DIR).expanduser().resolve()


def playbook() -> Path:
    return ansible_dir() / "site.yml"


def availability() -> tuple[bool, str]:
    """Можно ли запускать прогоны и, если нельзя, почему."""
    if not get_settings().ANSIBLE_DIR:
        return False, "В настройках не задан ANSIBLE_DIR — каталог со сценариями"

    if not playbook().is_file():
        return False, f"Нет плейбука {playbook()}"

    if shutil.which("ansible-playbook") is None:
        return False, "Рядом нет ansible-playbook — поднимите приложение из образа"

    return True, ""


def _group_vars() -> dict[str, Any]:
    """Переменные сценариев из `group_vars/all.yml`.

    Читаем их, а не дублируем у себя: что человек поменял в сценариях, то и предложит
    форма. Берём только простые скаляры — ключи с Jinja (`ansible_user`) нам не нужны.
    """
    path = ansible_dir() / "group_vars" / "all.yml"

    if not path.is_file():
        return {}

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        log.exception("Не удалось прочитать %s", path)
        return {}


def defaults() -> ProvisionDefaults:
    """Значения для формы поднятия сервера.

    Пользователь и порт берутся из `.env`, если заданы там: сценарии лежат в публичном
    репозитории, и личные значения в них не хранятся. Остальное — из `group_vars`.
    """
    available, reason = availability()
    settings = get_settings()
    values = _group_vars()

    return ProvisionDefaults(
        available=available,
        reason=reason,
        admin_user=settings.PROVISION_ADMIN_USER or str(values.get("admin_user", "")),
        ssh_port=settings.PROVISION_SSH_PORT or int(values.get("ssh_port", 22)),
        bootstrap_user=str(values.get("bootstrap_user", "root")),
        xui_port=int(values.get("xui_panel_port", 2053)),
        awg_port=int(values.get("awg_ui_port", 8080)),
        awg_vpn_ports=[int(port) for port in values.get("awg_vpn_ports", [])],
    )


# ---------------------------------------------------------------------- #
# Проверка ввода и создание прогона
# ---------------------------------------------------------------------- #


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False

    return True


def _check_host(host: str) -> None:
    if not _is_ip(host) and not HOSTNAME_RE.match(host):
        raise _bad_request(f"«{host}» не похож ни на IP, ни на имя хоста")


def _check_port(port: int, name: str) -> None:
    if not 1 <= port <= 65535:
        raise _bad_request(f"{name}: порт вне диапазона 1–65535")


def validate(data: ProvisionIn) -> None:
    """Проверяет всё, что уедет в плейбук и в `servers.yml`.

    Ключ проверяем теми же правилами, что и при добавлении готового сервера: он ляжет
    в базу у каждого конфига. Остальное — потому что уезжает в команды на сервере и
    в правила UFW, а не только в наши файлы.
    """
    if not SERVER_KEY_RE.match(data.key):
        raise _bad_request(
            "Ключ сервера: строчные латинские буквы, цифры, дефис и подчёркивание"
        )

    if srv.find_server(data.key) is not None:
        raise _bad_request(f"Сервер с ключом {data.key} уже есть")

    if not data.title.strip():
        raise _bad_request("Название обязательно")

    _check_host(data.host)
    _check_port(data.ssh_port, "SSH")

    if data.panel_port:
        _check_port(data.panel_port, "Панель")

    for user, name in ((data.admin_user, "Пользователь"), (data.bootstrap_user, "Первый вход")):
        if not UNIX_USER_RE.match(user):
            raise _bad_request(f"{name}: имя пользователя Linux (строчные буквы, цифры, _ и -)")

    if data.panel_password and len(data.panel_password) < MIN_PANEL_PASSWORD:
        raise _bad_request(
            f"Пароль панели короче {MIN_PANEL_PASSWORD} символов — плейбук такой не примет"
        )

    for port in data.open_ports:
        if not OPEN_PORT_RE.match(port):
            raise _bad_request(f"Порт inbound'а «{port}»: ожидается 443 или 443/tcp")

    for port in data.vpn_ports:
        _check_port(port, "VPN")


def create_run(db: Session, data: ProvisionIn) -> ProvisionRun:
    """Создаёт строку прогона: по ней страница вернётся к нему после перезагрузки."""
    run = ProvisionRun(
        server_key=data.key,
        title=data.title.strip(),
        host=data.host,
        panel=data.panel.value,
        step="Запуск плейбука",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


# ---------------------------------------------------------------------- #
# Файлы прогона
# ---------------------------------------------------------------------- #


def base_dir() -> Path:
    """Каталог прогонов: в нём папка на прогон и общий `known_hosts`.

    Тоже абсолютным: пути отсюда уезжают в аргументы плейбука, а он работает в каталоге
    сценариев.
    """
    return Path(get_settings().PROVISION_DIR).expanduser().resolve()


def run_dir(run_id: int) -> Path:
    return base_dir() / str(run_id)


def log_path(run_id: int) -> Path:
    return run_dir(run_id) / "run.log"


def _write_private(path: Path, text: str) -> None:
    """Пишет файл сразу с правами 600: внутри пароли.

    Через `os.open`, а не `write_text` с последующим `chmod`: между созданием файла и
    сменой прав есть окно, в которое его успеет прочитать кто угодно.
    """
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

    with os.fdopen(descriptor, "w", encoding="utf-8") as fh:
        fh.write(text)


def _inventory(data: ProvisionIn) -> dict[str, Any]:
    """Одноразовый inventory из одного хоста.

    `ansible_user`, `ansible_port` и пароль кладём именно сюда, а не в `-e`: плейбук
    сам решает, как заходить (открыт `ssh_port` — рабочим пользователем, нет — под
    `bootstrap_user` на 22), и делает это через `set_fact`. `set_fact` перебивает
    переменные хоста и **не** перебивает `-e`, поэтому в extra vars эти ключи сломали бы
    заход на свежий сервер.
    """
    host_vars: dict[str, Any] = {
        "ansible_host": data.host,
        "ansible_user": data.admin_user,
        "ansible_port": data.ssh_port,
    }

    if data.bootstrap_password:
        host_vars["ansible_ssh_pass"] = data.bootstrap_password

    return {"all": {"hosts": {f"{data.key}_server": host_vars}}}


def _web_path() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(WEB_PATH_LENGTH))


def panel_port(data: ProvisionIn) -> int:
    """Порт панели на сервере: заданный в форме либо из `group_vars` сценариев."""
    if data.panel_port:
        return data.panel_port

    values = _group_vars()

    if data.panel is ProvisionPanel.XUI:
        return int(values.get("xui_panel_port", 2053))

    return int(values.get("awg_ui_port", 8080))


def _extra_vars(data: ProvisionIn, password: str, web_path: str, port: int) -> dict[str, Any]:
    """Переменные прогона: панель, её доступы и порты.

    Пароль панели и `admin_password` уезжают файлом (`-e @vars.json`), а не строкой в
    командной строке: аргументы процесса видны в `ps` любому на машине.
    """
    values: dict[str, Any] = {
        "admin_user": data.admin_user,
        "ssh_port": data.ssh_port,
        "bootstrap_user": data.bootstrap_user,
    }

    if data.admin_password:
        values["admin_password"] = data.admin_password

    if data.panel is ProvisionPanel.XUI:
        values |= {
            "vpn_panels": ["3x-ui"],
            "xui_admin_password": password,
            # Путь панели задаём сами: иначе плейбук сгенерирует случайный и напечатает
            # его в лог один раз, а он нужен нам в base_url.
            "xui_web_base_path": web_path,
            "xui_panel_port": port,
            "xui_open_ports": data.open_ports,
        }
    else:
        values |= {
            "vpn_panels": ["amneziawg"],
            "awg_ui_password": password,
            "awg_ui_port": port,
        }

        if data.vpn_ports:
            values["awg_vpn_ports"] = data.vpn_ports

    return values


class PreparedRun(NamedTuple):
    """Что подготовлено к прогону: файлы для ansible и доступы для `servers.yml`."""

    inventory: Path
    variables: Path
    password: str
    web_path: str


def prepare(run: ProvisionRun, data: ProvisionIn) -> PreparedRun:
    """Готовит каталог прогона: inventory, переменные и пустой лог.

    Пароль панели и путь панели возвращаются сюда же: они нужны и подпроцессу, и записи
    сервера в `servers.yml` по успеху.
    """
    directory = run_dir(run.id)
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)

    password = data.panel_password or secrets.token_urlsafe(PANEL_PASSWORD_BYTES)
    web_path = _web_path() if data.panel is ProvisionPanel.XUI else ""

    inventory = directory / "inventory.yml"
    variables = directory / "vars.json"

    _write_private(inventory, yaml.safe_dump(_inventory(data), allow_unicode=True))
    _write_private(
        variables,
        json.dumps(_extra_vars(data, password, web_path, panel_port(data)), ensure_ascii=False),
    )
    _write_private(log_path(run.id), "")

    return PreparedRun(inventory, variables, password, web_path)


def cleanup(run_id: int) -> None:
    """Убирает файлы с доступами, лог оставляет: он нужен странице и после прогона."""
    for name in ("inventory.yml", "vars.json"):
        (run_dir(run_id) / name).unlink(missing_ok=True)


# ---------------------------------------------------------------------- #
# Лог
# ---------------------------------------------------------------------- #


def read_log(run_id: int, offset: int = 0) -> tuple[int, str]:
    """Кусок лога после смещения и новое смещение.

    Смещение в байтах: страница присылает то, что получила в прошлый раз, и дописывает
    пришедшее в конец. Так лог не переливается целиком на каждом тике полинга.
    """
    path = log_path(run_id)

    if not path.is_file():
        return 0, ""

    with path.open("rb") as fh:
        fh.seek(max(offset, 0))
        chunk = fh.read(LOG_CHUNK)
        return fh.tell(), chunk.decode("utf-8", errors="replace")


def log_tail(run_id: int, lines: int = ERROR_TAIL_LINES) -> str:
    """Последние строки лога — в текст ошибки упавшего прогона."""
    path = log_path(run_id)

    if not path.is_file():
        return ""

    text = path.read_text(encoding="utf-8", errors="replace")

    return "\n".join(text.splitlines()[-lines:])


# ---------------------------------------------------------------------- #
# Запись сервера в servers.yml
# ---------------------------------------------------------------------- #


def _server_create(data: ProvisionIn, password: str, web_path: str) -> ServerCreate:
    """Сервер для `servers.yml` по тому, что мы сами и настроили.

    Выключенным: свежая панель ещё не проверена, а у 3x-ui на ней к тому же нет ни
    одного inbound'а. Включает человек переключателем, убедившись кнопкой «Проверить».

    Ключ SSH не прописываем: путь к нему разный на хосте и в контейнере (`~` там и там
    свой), а paramiko сам найдёт `~/.ssh/id_*` и спросит агент.
    """
    port = panel_port(data)
    values = _group_vars()
    ssh = SshConfig(host=data.host, user=data.admin_user, port=data.ssh_port)

    if data.panel is ProvisionPanel.AMNEZIAWG:
        return ServerCreate(
            key=data.key,
            title=data.title.strip(),
            panel=PanelKind.AMNEZIA,
            transport=TransportKind.SSH,
            enabled=False,
            base_url=f"http://127.0.0.1:{port}",
            ssh=ssh,
            auth=PanelAuth(username=str(values.get("awg_ui_user", "admin")), password=password),
        )

    return ServerCreate(
        key=data.key,
        title=data.title.strip(),
        panel=PanelKind.XUI,
        transport=TransportKind.SSH,
        enabled=False,
        base_url=f"http://127.0.0.1:{port}/{web_path}/",
        # На свежей панели inbound'ов нет вовсе; единица — то, чем станет первый
        # созданный. Пока его не создали, проверка честно скажет, что клиентов не нашла.
        inbound_ids=[1],
        ssh=ssh,
        auth=PanelAuth(username=str(values.get("xui_admin_user", "admin")), password=password),
    )


def register(data: ProvisionIn, password: str, web_path: str) -> None:
    """Дописывает поднятый сервер в `servers.yml`.

    Пользуемся обычным добавлением сервера: проверка ключа, запись ruamel'ом с
    сохранением комментариев и сброс кеша там уже есть.
    """
    srv.add_server(_server_create(data, password, web_path))


def read_run(
    run: ProvisionRun,
    offset: int = 0,
    password: str = "",
    *,
    with_log: bool = True,
) -> ProvisionRunRead:
    """Строка прогона для интерфейса: состояние, кусок лога и куда идти за панелью.

    Списку прогонов лог не нужен (`with_log=False`): десять прогонов по 64 КБ в одном
    ответе — это мегабайт на открытие страницы, а показывает она лог одного.
    """
    result = ProvisionRunRead.model_validate(run)
    result.panel_password = password

    if with_log:
        result.offset, result.chunk = read_log(run.id, offset)

    if run.registered:
        result.tunnel, result.panel_url = access_hints(run.server_key)

    return result


def access_hints(key: str) -> tuple[str, str]:
    """Команда SSH-туннеля и адрес панели в браузере.

    Панель слушает только localhost сервера, поэтому иначе до неё не добраться — а зайти
    надо: у 3x-ui создать inbound, у AmneziaWG проверить сервер панели.
    """
    server = srv.find_server(key)

    if server is None or server.ssh is None:
        return "", ""

    parsed = urlparse(server.base_url)
    port = parsed.port or 80
    ssh = server.ssh
    target = f"{ssh.user}@{ssh.host}" if ssh.user else ssh.host

    tunnel = f"ssh -N -L {port}:127.0.0.1:{port} -p {ssh.port or 22} {target}"

    return tunnel, f"http://localhost:{port}{parsed.path}"
