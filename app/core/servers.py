"""Конфигурация VPN-серверов, с которых берутся конфиги.

Серверов несколько, панели у них разные, и настройки у каждой свои — в плоские
переменные `.env` это не укладывается, поэтому список живёт отдельным YAML-файлом
(путь в `VPN_SERVERS_FILE`). `.env` остаётся для того, что глобально на приложение:
SMTP, база, CORS.

Ключ сервера (`key`) — идентификатор на все случаи: он лежит в БД у каждого конфига,
приезжает на фронт и подставляется в кнопки генерации. Менять его после того, как
кампании созданы, нельзя — конфиги потеряют связь с сервером.
"""

from __future__ import annotations

import enum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class PanelKind(enum.StrEnum):
    """Тип панели на сервере — определяет, каким адаптером с ним говорить."""

    AMNEZIA = "amnezia"
    XUI = "3x-ui"
    WG_EASY = "wg-easy"
    FAKE = "fake"


class TransportKind(enum.StrEnum):
    """Как достучаться до API панели."""

    # Панель слушает localhost сервера — ходим curl'ом внутри SSH-сессии.
    SSH = "ssh"
    # Панель доступна снаружи — ходим обычным HTTP-клиентом.
    DIRECT = "direct"


class ArtifactKind(enum.StrEnum):
    """Что панель отдаёт получателю."""

    FILE = "file"  # файл .conf — уедет вложением
    LINK = "link"  # ссылка подписки — уедет текстом в теле письма


# Какой артефакт даёт каждая панель. Для заглушки задаётся явно в конфиге.
_PANEL_ARTIFACTS: dict[PanelKind, ArtifactKind] = {
    PanelKind.AMNEZIA: ArtifactKind.FILE,
    PanelKind.WG_EASY: ArtifactKind.FILE,
    PanelKind.XUI: ArtifactKind.LINK,
}


class SshConfig(BaseModel):
    """Как подключаться к серверу по SSH.

    `host` — либо алиас из `~/.ssh/config`, либо обычное имя хоста. Всё, что задано
    здесь явно, перекрывает найденное в `~/.ssh/config`.
    """

    host: str
    use_ssh_config: bool = True
    config_path: str = "~/.ssh/config"
    user: str = ""
    port: int | None = None
    key_file: str = ""
    key_passphrase: str = ""
    password: str = ""
    timeout: int = 30


class PanelAuth(BaseModel):
    """Доступ к API панели.

    У 3x-ui это Bearer-токен из Settings → Security → API Token (на старых версиях
    токена нет — там логин с паролем и cookie-сессия). У wg-easy v15 — логин и пароль
    от веб-морды через Basic Auth. У AmneziaWG — логин и пароль от панели.
    """

    token: str = ""
    username: str = ""
    password: str = ""


class ServerConfig(BaseModel):
    """Один VPN-сервер: где он, какая на нём панель и как в неё ходить."""

    key: str
    title: str
    panel: PanelKind
    transport: TransportKind
    enabled: bool = True

    # Адрес API панели. Для transport=ssh это localhost-адрес на самом сервере.
    base_url: str = "http://127.0.0.1:8080"

    ssh: SshConfig | None = None
    auth: PanelAuth = Field(default_factory=PanelAuth)

    # 3x-ui: в какие inbound'ы заводить клиента. На старых версиях панели имя клиента
    # уникально в пределах всей панели, поэтому там список из одного inbound'а.
    inbound_ids: list[int] = Field(default_factory=list)

    # 3x-ui: значение flow у новых клиентов, например xtls-rprx-vision. Пусто — берём
    # то, что уже стоит у клиентов этого inbound'а: flow задаётся не вкусом, а
    # протоколом inbound'а, и у соседей по нему он заведомо правильный.
    flow: str = ""

    # 3x-ui: база ссылки подписки, например https://sub.example.com/subs/. Пусто —
    # спрашиваем саму панель (её настройки subURI/subDomain/subPort/subPath). Задать
    # явно стоит, когда панель за прокси и её собственные настройки врут про адрес.
    sub_base: str = ""

    # AmneziaWG: id сервера внутри панели. Пусто — берём единственный существующий.
    panel_server_id: str = ""

    # Проверять ли TLS-сертификат панели при transport=direct.
    verify_tls: bool = True

    # Заглушка (panel=fake) сама по себе не знает, что изображает.
    artifact: ArtifactKind | None = None

    @model_validator(mode="after")
    def _check(self) -> ServerConfig:
        if self.transport is TransportKind.SSH and self.ssh is None:
            raise ValueError(f"Сервер {self.key}: при transport=ssh нужен блок ssh")

        if self.panel is PanelKind.FAKE and self.artifact is None:
            raise ValueError(f"Сервер {self.key}: при panel=fake нужно указать artifact")

        if self.panel is PanelKind.XUI and not self.inbound_ids:
            raise ValueError(f"Сервер {self.key}: для 3x-ui нужен непустой inbound_ids")

        return self

    @property
    def artifact_kind(self) -> ArtifactKind:
        """Что этот сервер отдаёт получателю — файл или ссылку."""
        if self.artifact is not None:
            return self.artifact
        return _PANEL_ARTIFACTS[self.panel]


class ServersConfig(BaseModel):
    """Полный список серверов из YAML-файла."""

    servers: list[ServerConfig]

    @model_validator(mode="after")
    def _unique_keys(self) -> ServersConfig:
        keys = [s.key for s in self.servers]
        duplicates = {key for key in keys if keys.count(key) > 1}
        if duplicates:
            raise ValueError(f"Повторяющиеся ключи серверов: {', '.join(sorted(duplicates))}")
        return self

    @property
    def enabled(self) -> list[ServerConfig]:
        """Только включённые серверы — именно на них заводятся конфиги."""
        return [s for s in self.servers if s.enabled]


def load_servers(path: str) -> ServersConfig:
    """Читает YAML со списком серверов.

    Файла может не быть (свежий клон, дев без доступа к серверам) — тогда список пуст,
    приложение поднимается, а генерация конфигов честно скажет, что серверов нет.
    """
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        return ServersConfig(servers=[])

    with file_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return ServersConfig.model_validate(raw)


@lru_cache
def get_servers(path: str) -> ServersConfig:
    """Кешированный список серверов: файл читается один раз за жизнь процесса."""
    return load_servers(path)
