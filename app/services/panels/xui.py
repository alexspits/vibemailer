"""3x-ui: ссылка подписки на клиента.

Версия панели определяется в рантайме. У свежих есть первоклассный REST по
`/panel/api/clients/*`, где клиент — самостоятельная сущность и одним вызовом
цепляется сразу к нескольким inbound'ам. У старых такого нет: клиент живёт внутри
inbound'а, и завести его можно только через `/panel/api/inbounds/addClient`, передав
блок `settings` JSON-строкой. Пробуем новый путь, при 404 откатываемся на старый.

Авторизация от версии не зависит и выбирается отдельно: если в конфиге задан
`auth.token` — ходим с Bearer (его дают Settings → Security → API Token, и CSRF для
него не нужен), иначе логинимся через `POST /login` и живём на cookie-сессии.

Ссылка подписки собирается из настроек панели (`subURI` либо `subDomain`/`subPort`/
`subPath`) и `subId` клиента. База одна на панель, поэтому запрашивается один раз.
Путь к самим настройкам от версии тоже зависит (`/panel/api/setting/all` против
`/panel/setting/all`) — пробуем оба. Если панель стоит за прокси и врёт про свой адрес,
базу можно задать в `servers.yml` (`sub_base`) и панель об этом не спрашивать вовсе.

`subId` при создании задаём равным имени конфига — панель отдаёт подписку именно по
нему, и ссылка получается читаемой (`.../sub/alice1`), а не со случайным хвостом.
Путь подписки при этом остаётся тем, что настроен в панели, — его мы не трогаем.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from typing import TYPE_CHECKING
from urllib.parse import quote, urlparse

from app.services.panels.base import Artifact, BasePanel, PanelError

if TYPE_CHECKING:
    from app.services.transport import Response

log = logging.getLogger("vibe_mail.panels.xui")

DEFAULT_SUB_PATH = "/sub/"

# Настройки панели: у свежих версий они под /panel/api/, у прежних — прямо в /panel/.
SETTINGS_PATHS = ("/panel/api/setting/all", "/panel/setting/all")


def _unwrap_client(obj: object) -> dict | None:
    """Запись клиента из ответа панели; None — её там нет.

    `clients/get` заворачивает клиента ещё раз: `obj` — это `{"client": {...}}`, а не
    сам клиент. У `clients/list` записи лежат плоско. Разбираем оба вида, чтобы не
    зависеть от того, какой эндпоинт спросили.
    """
    if not isinstance(obj, dict):
        return None

    inner = obj.get("client")
    if isinstance(inner, dict):
        return inner

    return obj if "email" in obj or "subId" in obj else None


def _envelope(response: Response) -> dict | None:
    """Ответ как конверт 3x-ui `{success, msg, obj}`; None — это не он.

    Нужно там, где ответ проверяется, а не разбирается: панель на неизвестный путь
    отвечает и 404, и редиректом на страницу входа, и HTML со статусом 200.
    """
    if not response.is_ok:
        return None

    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) and "success" in payload else None


class XuiPanel(BasePanel):
    """Клиенты 3x-ui через API панели."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._is_modern: bool | None = None
        # flow спрашиваем у панели один раз за сессию: он один на inbound.
        self._flow_value: str | None = None
        self._sub_base: str | None = None
        self._logged_in = False

    # ------------------------------------------------------------------ #
    # Авторизация
    # ------------------------------------------------------------------ #

    def _auth_headers(self) -> dict[str, str]:
        if self.server.auth.token:
            return {"Authorization": f"Bearer {self.server.auth.token}"}
        return {}

    def _login(self) -> None:
        """Вход с логином и паролем — только когда токена нет. Cookie хранит транспорт."""
        if self.server.auth.token or self._logged_in:
            return

        response = self._request(
            "POST",
            "/login",
            json_body={
                "username": self.server.auth.username,
                "password": self.server.auth.password,
            },
        )

        if not response.is_ok:
            raise PanelError(
                f"Панель {self.server.title} не пустила: {response.status} {response.body[:200]}"
            )

        payload = response.json()
        if isinstance(payload, dict) and not payload.get("success", True):
            raise PanelError(
                f"Панель {self.server.title} отклонила логин: {payload.get('msg', '')}"
            )

        self._logged_in = True

    # ------------------------------------------------------------------ #
    # Запросы
    # ------------------------------------------------------------------ #

    def _call(self, method: str, path: str, json_body: object | None = None) -> Response:
        """Сырой ответ панели — нужен там, где важен сам код (определение версии)."""
        self._login()
        return self._request(method, path, json_body=json_body)

    def _api(self, method: str, path: str, json_body: object | None = None) -> object:
        """Запрос с разбором конверта `{success, msg, obj}`."""
        response = self._call(method, path, json_body)

        if not response.is_ok:
            raise PanelError(
                f"Панель {self.server.title} ответила {response.status}: {response.body[:200]}"
            )

        payload = response.json()

        if not isinstance(payload, dict):
            raise PanelError(f"Панель вернула неожиданный ответ: {response.body[:200]}")

        if not payload.get("success", False):
            raise PanelError(f"Панель отказала: {payload.get('msg') or response.body[:200]}")

        return payload.get("obj")

    def _modern(self) -> bool:
        """Есть ли на панели новый API клиентов. Проверяется один раз за сессию.

        Признак — не «ответ не 404», а разобранный конверт: на неизвестный путь панель
        отвечает по-разному, и редирект на страницу входа (HTML со статусом 200) сошёл
        бы за новый API. Ошибка авторизации тоже уводит на старый путь — там она
        повторится и скажет про себя внятно, кодом ответа.
        """
        if self._is_modern is None:
            response = self._call("GET", "/panel/api/clients/list")
            self._is_modern = _envelope(response) is not None
            log.info(
                "Панель %s: используем %s API 3x-ui",
                self.server.key,
                "новый" if self._is_modern else "старый",
            )

        return self._is_modern

    # ------------------------------------------------------------------ #
    # Ссылка подписки
    # ------------------------------------------------------------------ #

    def _subscription_base(self) -> str:
        """База ссылки подписки — одна на панель, поэтому спрашиваем один раз."""
        if self._sub_base is not None:
            return self._sub_base

        if self.server.sub_base:
            # Задано в конфиге — панель не спрашиваем: за прокси её собственные
            # настройки показывают внутренний адрес, а не тот, по которому ходит клиент.
            self._sub_base = self.server.sub_base.rstrip("/") + "/"
            return self._sub_base

        self._sub_base = self._build_sub_base(self._panel_settings())
        return self._sub_base

    def _panel_settings(self) -> dict:
        """Настройки панели. Путь к ним зависит от версии, поэтому пробуем оба."""
        failures: list[str] = []

        for path in SETTINGS_PATHS:
            response = self._call("POST", path)
            payload = _envelope(response)

            if payload is None:
                failures.append(f"{path} → {response.status}")
                continue

            if not payload.get("success"):
                failures.append(f"{path} → {payload.get('msg') or 'отказ панели'}")
                continue

            settings = payload.get("obj")

            if isinstance(settings, dict):
                return settings

            failures.append(f"{path} → в ответе нет настроек")

        raise PanelError(
            f"Панель {self.server.title}: не удалось прочитать настройки подписки "
            f"({'; '.join(failures)}). Задайте sub_base в servers.yml — тогда ссылка "
            "соберётся без обращения к панели."
        )

    def _build_sub_base(self, settings: dict) -> str:
        """Собирает базу ссылки: либо готовый subURI, либо домен, порт и путь."""
        sub_uri = str(settings.get("subURI") or "").strip()

        if not sub_uri:
            sub_uri = self._compose_sub_uri(settings)

        return sub_uri.rstrip("/") + "/"

    def _compose_sub_uri(self, settings: dict) -> str:
        """База подписки из отдельных настроек, когда subURI в панели не задан."""
        # Свой сертификат у подписки — значит, она отдаётся по https.
        scheme = "https" if settings.get("subCertFile") else "http"

        domain = str(settings.get("subDomain") or "").strip()
        if not domain:
            # Домен подписки в панели не настроен — берём хост самой панели.
            domain = urlparse(self.server.base_url).hostname or ""
            log.warning(
                "Панель %s: subDomain не задан, ссылка подписки собирается по хосту панели (%s)",
                self.server.key,
                domain or "?",
            )

        if not domain:
            raise PanelError(
                f"Панель {self.server.title}: не удалось определить домен подписки — "
                "задайте subURI или subDomain в настройках панели"
            )

        port = settings.get("subPort")
        path = str(settings.get("subPath") or DEFAULT_SUB_PATH)
        host = f"{domain}:{port}" if port else domain

        return f"{scheme}://{host}{path}"

    # ------------------------------------------------------------------ #
    # Список клиентов
    # ------------------------------------------------------------------ #

    def _modern_client_names(self) -> list[str]:
        clients = self._api("GET", "/panel/api/clients/list")

        if not isinstance(clients, list):
            raise PanelError("Панель вернула неожиданный ответ на список клиентов")

        return [client["email"] for client in clients if client.get("email")]

    def _inbounds(self) -> list[dict]:
        inbounds = self._api("GET", "/panel/api/inbounds/list")

        if not isinstance(inbounds, list):
            raise PanelError("Панель вернула неожиданный ответ на список inbound'ов")

        return inbounds

    def _legacy_clients(self) -> list[dict]:
        """На старых панелях клиенты спрятаны в settings-JSON каждого inbound'а."""
        return [client for inbound in self._inbounds() for client in self._clients_of(inbound)]

    def _legacy_client_names(self) -> list[str]:
        return [client["email"] for client in self._legacy_clients() if client.get("email")]

    @staticmethod
    def _clients_of(inbound: dict) -> list[dict]:
        """Клиенты одного inbound'а. Кривой settings — просто пустой список."""
        try:
            settings = json.loads(inbound.get("settings") or "{}")
        except json.JSONDecodeError:
            return []

        clients = settings.get("clients")
        return clients if isinstance(clients, list) else []

    def list_client_names(self) -> list[str]:
        if self._modern():
            return self._modern_client_names()
        return self._legacy_client_names()

    # ------------------------------------------------------------------ #
    # Создание клиента
    # ------------------------------------------------------------------ #

    def _flow(self) -> str:
        """Значение flow для нового клиента: из настроек либо от соседей по inbound'у.

        Без flow клиент на VLESS+Vision молча не работает: панель его создаёт, конфиг
        отдаёт, а соединение не встаёт. Правильное значение диктует протокол inbound'а,
        поэтому берём то, что уже стоит у клиентов этого же inbound'а, — угадывать
        нечего. Пустая строка тоже ответ: на inbound'ах без XTLS flow быть не должно.
        """
        if self._flow_value is not None:
            return self._flow_value

        if self.server.flow:
            self._flow_value = self.server.flow
            return self._flow_value

        wanted = set(self.server.inbound_ids)
        flows = Counter(
            client["flow"]
            for client in self._flow_source()
            if client.get("flow") and wanted.intersection(client.get("inboundIds") or [])
        )
        self._flow_value = flows.most_common(1)[0][0] if flows else ""

        log.info(
            "Панель %s: flow новых клиентов — %r",
            self.server.key,
            self._flow_value,
        )
        return self._flow_value

    def _flow_source(self) -> list[dict]:
        """Клиенты, у которых подсматриваем flow. На старом API их даёт список inbound'ов."""
        if not self._modern():
            return [
                dict(client, inboundIds=[inbound.get("id")])
                for inbound in self._inbounds()
                for client in self._clients_of(inbound)
            ]

        clients = self._api("GET", "/panel/api/clients/list")
        return clients if isinstance(clients, list) else []

    def _create_modern(self, name: str) -> str:
        """Новый API: остальные секреты генерирует панель, subId задаём мы.

        subId читаем обратно, а не считаем равным имени: панель вправе его почистить,
        и в ссылку должно попасть то, по чему подписка реально отдаётся.
        """
        self._api(
            "POST",
            "/panel/api/clients/add",
            {
                "client": {
                    "email": name,
                    "subId": name,
                    "enable": True,
                    "flow": self._flow(),
                },
                "inboundIds": self.server.inbound_ids,
            },
        )

        client = _unwrap_client(self._api("GET", f"/panel/api/clients/get/{quote(name, safe='')}"))

        if client is None or not client.get("subId"):
            # Перечисляем поля, но не значения: в записи клиента лежит его uuid,
            # а это и есть доступ. Текст ошибки уезжает в БД и на экран.
            fields = ", ".join(sorted(client)) if client else "ответ пуст"
            raise PanelError(f"Панель не вернула subId для {name} (поля ответа: {fields})")

        return client["subId"]

    def _create_legacy(self, name: str) -> str:
        """Старый API: клиент кладётся в каждый inbound, subId задаём равным имени.

        На старых панелях имя клиента уникально в пределах всей панели, а не inbound'а,
        поэтому список из нескольких inbound_ids здесь упрётся в «duplicate email» на
        втором. Ошибка при этом говорит, на каком именно inbound'е встала.
        """
        client = {
            "id": str(uuid.uuid4()),
            "email": name,
            "subId": name,
            "enable": True,
            "flow": self._flow(),
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0,
            "tgId": "",
        }

        for inbound_id in self.server.inbound_ids:
            try:
                self._api(
                    "POST",
                    "/panel/api/inbounds/addClient",
                    {"id": inbound_id, "settings": json.dumps({"clients": [client]})},
                )
            except PanelError as exc:
                raise PanelError(f"Клиент {name}, inbound {inbound_id}: {exc}") from exc

        return name

    def fetch_client(self, name: str) -> Artifact | None:
        """Ссылка подписки уже заведённого клиента либо None.

        У клиента, созданного руками, `subId` случайный — ссылка будет с ним, а не
        читаемая `.../sub/имя`. Переписывать `subId` не берёмся: `update` заменяет
        запись целиком, и мы затёрли бы поля, которых не знаем.
        """
        sub_id = self._existing_sub_id(name)

        if sub_id is None:
            return None

        if sub_id != name:
            log.info(
                "Клиент %s на %s заведён с subId %r — ссылка будет с ним",
                name,
                self.server.key,
                sub_id,
            )

        return Artifact.url(f"{self._subscription_base()}{quote(sub_id)}")

    def _existing_sub_id(self, name: str) -> str | None:
        """subId клиента по имени; None — такого клиента на панели нет."""
        if not self._modern():
            client = next(
                (c for c in self._legacy_clients() if c.get("email") == name),
                None,
            )
            return client.get("subId") if client else None

        payload = _envelope(self._call("GET", f"/panel/api/clients/get/{quote(name, safe='')}"))

        # Нет клиента, нет доступа, нет такого пути — здесь всё это одинаково значит
        # «взять нечего». Если дело в доступе, следом попытка создать клиента упрётся
        # в ту же причину и скажет о ней кодом ответа.
        if payload is None or not payload.get("success"):
            return None

        client = _unwrap_client(payload.get("obj"))
        return client.get("subId") if client else None

    def _create_client(self, name: str) -> Artifact:
        sub_id = self._create_modern(name) if self._modern() else self._create_legacy(name)

        if sub_id != name:
            log.warning(
                "Панель %s сохранила subId как %r вместо имени %r — ссылка будет с ним",
                self.server.key,
                sub_id,
                name,
            )

        link = f"{self._subscription_base()}{quote(sub_id)}"

        log.info("Клиент %s создан на %s", name, self.server.key)
        return Artifact.url(link)
