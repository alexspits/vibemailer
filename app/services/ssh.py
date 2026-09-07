"""Подключение к серверам по SSH.

Единственное место, где собираются аргументы `paramiko.connect()`. Paramiko сам
`~/.ssh/config` не читает — ни алиасы, ни `IdentityFile`, — поэтому файл разбираем
руками через `paramiko.SSHConfig` и раскладываем по аргументам подключения.

Порядок такой: сначала берём то, что нашлось в `~/.ssh/config` по алиасу, сверху
кладём явно заданное в `servers.yml`. Явное всегда выигрывает: конфиг серверов —
источник правды, `~/.ssh/config` лишь избавляет от переписывания хоста и ключа.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import paramiko

if TYPE_CHECKING:
    from app.core.servers import SshConfig

log = logging.getLogger("vibe_mail.ssh")

DEFAULT_PORT = 22


class SshError(Exception):
    """Не удалось подключиться по SSH или выполнить команду."""


def _lookup_ssh_config(alias: str, config_path: str) -> dict[str, Any]:
    """Секция `~/.ssh/config` для алиаса; пустой словарь, если файла нет.

    `SSHConfig.lookup` никогда не падает на незнакомом алиасе — возвращает его же
    в `hostname`, — так что отсутствие секции отдельно проверять не нужно.
    """
    path = Path(config_path).expanduser()
    if not path.is_file():
        return {}

    config = paramiko.SSHConfig()
    with path.open(encoding="utf-8") as fh:
        config.parse(fh)

    return config.lookup(alias)


def _first_identity_file(options: dict[str, Any]) -> str | None:
    """Первый `IdentityFile` из секции конфига, если он там есть."""
    identities = options.get("identityfile")
    if not identities:
        return None
    return str(Path(identities[0]).expanduser())


def _port_from(options: dict[str, Any]) -> int | None:
    """`Port` из секции конфига; кривое значение игнорируем, а не роняем подключение."""
    raw = options.get("port")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        log.warning("В ~/.ssh/config нечисловой Port=%r, беру порт по умолчанию", raw)
        return None


def build_connect_kwargs(ssh: SshConfig) -> dict[str, Any]:
    """Аргументы `paramiko.SSHClient.connect()` для сервера.

    Ключи ищем в трёх местах и именно в этом порядке: явный `key_file`, `IdentityFile`
    из `~/.ssh/config`, дальше — обычные `~/.ssh/id_*` и ssh-agent, которые paramiko
    подберёт сам. Пароль остаётся запасным вариантом: если он не задан, аутентификация
    идёт только по ключу.
    """
    options = _lookup_ssh_config(ssh.host, ssh.config_path) if ssh.use_ssh_config else {}

    key_file = ssh.key_file or _first_identity_file(options)

    kwargs: dict[str, Any] = {
        "hostname": options.get("hostname") or ssh.host,
        "port": ssh.port or _port_from(options) or DEFAULT_PORT,
        "username": ssh.user or options.get("user") or None,
        "timeout": ssh.timeout,
        # Ключ из конфига серверов или из ~/.ssh/config.
        "key_filename": key_file,
        "passphrase": ssh.key_passphrase or None,
        "password": ssh.password or None,
        # В отличие от прежнего поведения ключи и агент разрешены: без этого
        # подключение по ключу невозможно в принципе.
        "allow_agent": True,
        "look_for_keys": True,
    }

    return {name: value for name, value in kwargs.items() if value is not None}


def connect(ssh: SshConfig) -> paramiko.SSHClient:
    """Поднимает SSH-соединение по настройкам сервера."""
    client = paramiko.SSHClient()

    # Ключи хостов читаем из ~/.ssh/known_hosts: без них AutoAdd принимал бы **любой**
    # ключ на каждом подключении, то есть подмену сервера — а внутрь сессии уходит
    # пароль от панели и обратно приезжают приватные ключи конфигов.
    #
    # Политика мягкая намеренно: у наших серверов нестандартные порты, и ssh хранит
    # такие записи как `[хост]:порт`, а под старым именем ключ мог осесть как `хост`.
    # RejectPolicy сломала бы подключение к серверу, ключ которого записан в другой
    # форме. Смену уже известного ключа paramiko отвергнет при любой политике — именно
    # это и есть защита от подмены; неизвестный хост даст предупреждение в лог.
    with contextlib.suppress(OSError):
        client.load_system_host_keys()

    client.set_missing_host_key_policy(paramiko.WarningPolicy())

    kwargs = build_connect_kwargs(ssh)

    try:
        client.connect(**kwargs)
    except Exception as exc:
        raise SshError(f"Не удалось подключиться по SSH к {kwargs['hostname']}: {exc}") from exc

    log.info("SSH-соединение с %s установлено", kwargs["hostname"])
    return client
