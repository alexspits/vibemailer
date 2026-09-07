"""Транспорт до API панели: через SSH или напрямую.

Панели живут по-разному: AmneziaWG и wg-easy слушают только localhost сервера, и
достучаться до них можно лишь изнутри SSH-сессии, а 3x-ui у нас смотрит наружу.
Адаптерам панелей эта разница не нужна — они говорят «сделай POST туда-то», а как
именно запрос доедет, решает транспорт.

Cookie транспорт держит сам: старый API 3x-ui логинится через `POST /login` и дальше
ждёт cookie-сессию, и адаптеру не должно быть разницы, кто её хранит — httpx или мы.
"""

from __future__ import annotations

import base64
import json
import logging
import shlex
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Protocol

import httpx

from app.core.servers import TransportKind
from app.services.ssh import SshError, connect

if TYPE_CHECKING:
    import paramiko

    from app.core.servers import ServerConfig

log = logging.getLogger("vibe_mail.transport")

# Разделитель, которым curl дописывает код ответа в конец тела.
_STATUS_MARKER = "__VIBE_MAIL_STATUS__"


class TransportError(Exception):
    """Запрос до панели не доехал: нет связи, оборвалось соединение, кривой ответ."""


@dataclass
class Response:
    """Ответ панели в том виде, в каком он нужен адаптерам."""

    status: int
    body: str

    @property
    def is_ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> object:
        """Тело как JSON; иначе — ошибка с описанием ответа, но без него самого.

        Кусок тела в текст не кладём: ошибка сохраняется в БД и показывается в
        интерфейсе, а телом вполне может оказаться .conf с приватным ключом или
        страница входа с токеном. Для разбора хватает кода и размера.
        """
        try:
            return json.loads(self.body)
        except json.JSONDecodeError as exc:
            preview = "пусто" if not self.body.strip() else f"{len(self.body)} байт"
            raise TransportError(f"Панель вернула не JSON (код {self.status}, {preview})") from exc


class Transport(Protocol):
    """Общий интерфейс: запрос к API панели и закрытие соединения."""

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: object | None = None,
        form_body: dict[str, str] | None = None,
    ) -> Response: ...

    def close(self) -> None: ...


def _merge_headers(
    base: dict[str, str],
    extra: dict[str, str] | None,
    cookies: dict[str, str],
) -> dict[str, str]:
    """Итоговые заголовки запроса: базовые, потом заданные адаптером, потом cookie."""
    headers = dict(base)
    headers.update(extra or {})

    if cookies:
        headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())

    return headers


def basic_auth_header(username: str, password: str) -> dict[str, str]:
    """Заголовок HTTP Basic — так авторизуется wg-easy v15."""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@dataclass
class SshCurlTransport:
    """Запросы к панели как `curl` внутри SSH-сессии.

    Соединение переиспользуется между запросами и переподключается при обрыве: на
    пачке в несколько десятков конфигов это экономит столько же хендшейков.
    """

    server: ServerConfig
    _client: paramiko.SSHClient | None = field(default=None, init=False, repr=False)
    _cookies: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    # ------------------------------------------------------------------ #
    # SSH
    # ------------------------------------------------------------------ #

    def _ssh(self) -> paramiko.SSHClient:
        """Живое соединение: поднимает новое, если его нет или оно оборвалось."""
        transport = self._client.get_transport() if self._client else None
        if transport is not None and transport.is_active():
            return self._client

        self.close()
        try:
            self._client = connect(self.server.ssh)
        except SshError as exc:
            raise TransportError(str(exc)) from exc

        return self._client

    def _run(self, command: str) -> tuple[str, str]:
        """Выполняет команду на сервере, возвращает (stdout, stderr)."""
        client = self._ssh()
        timeout = self.server.ssh.timeout

        try:
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode(errors="replace")
            err = stderr.read().decode(errors="replace")
            code = stdout.channel.recv_exit_status()
        except Exception as exc:
            raise TransportError(f"Ошибка выполнения команды на сервере: {exc}") from exc

        # Ненулевой код curl — это сетевая проблема, а не HTTP-ошибка: коды ответа
        # мы разбираем сами, поэтому --fail здесь намеренно не используется.
        if code != 0:
            # Из stderr берём только строки самого curl: там же лежит дамп заголовков
            # ответа (-D /dev/stderr), а в нём может быть Set-Cookie с сессией панели.
            reason = "; ".join(
                line.strip() for line in err.splitlines() if line.startswith("curl:")
            )
            raise TransportError(
                f"curl на сервере завершился с кодом {code}: {reason or 'без объяснения'}"
            )

        return out, err

    # ------------------------------------------------------------------ #
    # Сборка и разбор
    # ------------------------------------------------------------------ #

    def _build_command(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: object | None,
        form_body: dict[str, str] | None,
    ) -> str:
        """Команда curl: код ответа дописывается в конец тела, заголовки — в stderr."""
        parts = [
            "curl", "-sS",
            "--max-time", str(self.server.ssh.timeout),
            "-X", method,
            # Заголовки ответа уезжают в stderr — оттуда достаём Set-Cookie.
            "-D", "/dev/stderr",
            # Код ответа дописываем в конец stdout: отдельного канала под него нет.
            "-w", f"\\n{_STATUS_MARKER}%{{http_code}}",
        ]  # fmt: skip

        if not self.server.verify_tls:
            parts.append("-k")

        for name, value in headers.items():
            parts += ["-H", f"{name}: {value}"]

        if json_body is not None:
            parts += [
                "-H", "Content-Type: application/json",
                "-d", json.dumps(json_body, ensure_ascii=False),
            ]  # fmt: skip
        elif form_body is not None:
            for name, value in form_body.items():
                parts += ["--data-urlencode", f"{name}={value}"]

        parts.append(url)
        return " ".join(shlex.quote(part) for part in parts)

    @staticmethod
    def _split_status(out: str) -> Response:
        """Отрезает от тела код ответа, который дописал curl через -w."""
        marker = f"\n{_STATUS_MARKER}"
        body, _, raw_status = out.rpartition(marker)

        if not raw_status:
            raise TransportError(f"curl не вернул код ответа: {out[:200]}")

        try:
            status = int(raw_status.strip())
        except ValueError as exc:
            raise TransportError(f"curl вернул нечисловой код ответа: {raw_status[:50]}") from exc

        return Response(status=status, body=body)

    def _store_cookies(self, header_dump: str) -> None:
        """Забирает Set-Cookie из дампа заголовков — сессию храним у себя."""
        for line in header_dump.splitlines():
            if not line.lower().startswith("set-cookie:"):
                continue

            cookie = SimpleCookie()
            cookie.load(line.partition(":")[2].strip())
            for name, morsel in cookie.items():
                self._cookies[name] = morsel.value

    # ------------------------------------------------------------------ #
    # Публичное API
    # ------------------------------------------------------------------ #

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: object | None = None,
        form_body: dict[str, str] | None = None,
    ) -> Response:
        url = f"{self.server.base_url.rstrip('/')}{path}"
        all_headers = _merge_headers({}, headers, self._cookies)

        command = self._build_command(method, url, all_headers, json_body, form_body)
        out, err = self._run(command)

        self._store_cookies(err)
        return self._split_status(out)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


@dataclass
class DirectTransport:
    """Обычные HTTP-запросы к панели, доступной снаружи."""

    server: ServerConfig
    _client: httpx.Client | None = field(default=None, init=False, repr=False)

    def _http(self) -> httpx.Client:
        """Ленивый httpx-клиент: cookie и keep-alive он держит сам."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.server.base_url.rstrip("/"),
                verify=self.server.verify_tls,
                timeout=30.0,
                follow_redirects=True,
            )

        return self._client

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: object | None = None,
        form_body: dict[str, str] | None = None,
    ) -> Response:
        try:
            response = self._http().request(
                method,
                path,
                headers=headers,
                json=json_body,
                data=form_body,
            )
        except httpx.HTTPError as exc:
            raise TransportError(f"Не удалось обратиться к панели: {exc}") from exc

        return Response(status=response.status_code, body=response.text)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def build_transport(server: ServerConfig) -> Transport:
    """Транспорт под настройку сервера."""
    if server.transport is TransportKind.SSH:
        return SshCurlTransport(server=server)

    return DirectTransport(server=server)
