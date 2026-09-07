"""Заглушка панели — чтобы разрабатывать без доступа к серверам.

Отдаёт то же, что настоящая панель: файл либо ссылку подписки, смотря что задано в
`artifact` у сервера. Выданные клиенты запоминаются в памяти процесса и общие на ключ
сервера, поэтому повторный запрос того же имени возвращает тот же артефакт — как и на
живой панели. Живут они только до перезапуска приложения.
"""

from __future__ import annotations

import base64
import logging
import secrets
import time
from collections import defaultdict

from app.core.servers import ArtifactKind
from app.services.panels.base import Artifact, BasePanel

log = logging.getLogger("vibe_mail.panels.fake")

# Имитация похода на сервер, чтобы прогресс генерации был виден в интерфейсе.
DELAY = 0.4
SERVER_PUBLIC_KEY = "Zx1nKX0m6cQqvJHrGF3lTt5yWb8aNdPeS7uAoV2gYkM="

# Выданные артефакты по ключу сервера: «сервер» → «имя клиента» → артефакт.
# Состояние общее на процесс, а не на экземпляр: у настоящей панели оно живёт на
# сервере, и адаптеры, созданные в разных местах (воркер, запрос из интерфейса),
# обязаны видеть одно и то же. Иначе заглушка врёт именно там, где её и проверяют.
_CLIENTS: dict[str, dict[str, Artifact]] = defaultdict(dict)


class FakePanel(BasePanel):
    """Правдоподобные конфиги и ссылки со случайными ключами."""

    @property
    def _created(self) -> dict[str, Artifact]:
        """Клиенты «этого сервера» — общие для всех экземпляров адаптера."""
        return _CLIENTS[self.server.key]

    @staticmethod
    def _random_key() -> str:
        return base64.b64encode(secrets.token_bytes(32)).decode()

    def list_client_names(self) -> list[str]:
        return list(self._created)

    def fetch_client(self, name: str) -> Artifact | None:
        return self._created.get(name)

    def _wireguard_config(self) -> bytes:
        content = (
            "[Interface]\n"
            f"PrivateKey = {self._random_key()}\n"
            f"Address = 10.8.0.{secrets.randbelow(253) + 2}/32\n"
            "DNS = 1.1.1.1\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {SERVER_PUBLIC_KEY}\n"
            f"PresharedKey = {self._random_key()}\n"
            "AllowedIPs = 0.0.0.0/0, ::/0\n"
            f"Endpoint = vpn.example.com:{secrets.randbelow(20000) + 40000}\n"
            "PersistentKeepalive = 25\n"
        )
        return content.encode()

    def _create_client(self, name: str) -> Artifact:
        time.sleep(DELAY)

        log.info("Сгенерирован фейковый конфиг %s (%s)", name, self.server.key)

        if self.server.artifact_kind is ArtifactKind.FILE:
            artifact = Artifact.file(name, self._wireguard_config())
        else:
            # Имя в ссылке, как у настоящей 3x-ui: subId там равен имени конфига.
            artifact = Artifact.url(f"https://sub.example.com/sub/{name}")

        self._created[name] = artifact
        return artifact

    def close(self) -> None:
        """Закрывать нечего — транспорта у заглушки нет."""
