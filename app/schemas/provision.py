"""Pydantic-схемы поднятия нового сервера плейбуком.

Наружу отдаётся всё, что нужно показать на странице: состояние прогона, текущий шаг и
кусок лога. Доступы приезжают сюда на запуск и обратно не возвращаются — кроме пароля
панели, который программа сгенерировала сама: его человек видит один раз, пока прогон
живёт в памяти процесса, а дальше он лежит только в `servers.yml`.
"""

import enum
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import ProvisionStatus


class ProvisionPanel(enum.StrEnum):
    """Панель, которую ставит плейбук. Значения — те же, что в его `vpn_panels`."""

    XUI = "3x-ui"
    AMNEZIAWG = "amneziawg"


class ProvisionDefaults(BaseModel):
    """Что подставить в форму: прочитано из `group_vars/all.yml` самих сценариев.

    Источник правды один — файл сценариев: что человек поменял у себя в `group_vars`,
    то и предложит форма, а обратно уедет явным значением.
    """

    # Можно ли запускать прогоны: есть каталог со сценариями и сам ansible-playbook.
    available: bool
    # Почему нельзя — показывается подсказкой у выключенной кнопки.
    reason: str = ""

    admin_user: str = ""
    ssh_port: int = 22
    bootstrap_user: str = "root"

    # Порты панелей на самом сервере (панель слушает localhost, ходим через SSH).
    xui_port: int = 2053
    awg_port: int = 8080
    # UDP-порты, которые плейбук откроет под VPN-серверы AmneziaWG.
    awg_vpn_ports: list[int] = Field(default_factory=list)


class ProvisionIn(BaseModel):
    """Тело запроса на прогон плейбука по новому серверу."""

    # Ключ и название, под которыми сервер допишется в servers.yml по успеху прогона.
    key: str
    title: str
    # IP или имя хоста. В ~/.ssh/config его может не быть — доступы уедут в servers.yml
    # явными полями.
    host: str
    panel: ProvisionPanel

    # Кем и на каком порту сервер будет жить после настройки.
    admin_user: str
    ssh_port: int

    # Первый вход на свежий сервер: у хостеров это root или ubuntu на 22.
    bootstrap_user: str = "root"
    # Пусто — вход по ключу (хостер уже положил его в authorized_keys).
    bootstrap_password: str = ""

    # Пароль рабочего пользователя. Нужен только для входа через VNC-консоль хостера,
    # если SSH сломается; по SSH вход всё равно только по ключу.
    admin_password: str = ""

    # Пароль от веб-морды панели. Пусто — сгенерируем сами.
    panel_password: str = ""
    # Порт панели на сервере. 0 — взять из group_vars сценариев.
    panel_port: int = 0

    # 3x-ui: порты inbound'ов, которые откроет UFW («443/tcp», «8443»).
    open_ports: list[str] = Field(default_factory=list)
    # AmneziaWG: UDP-порты VPN-серверов панели.
    vpn_ports: list[int] = Field(default_factory=list)


class ProvisionRunRead(BaseModel):
    """Состояние прогона плюс кусок лога после запрошенного смещения."""

    id: int
    server_key: str
    title: str
    host: str
    panel: str
    status: ProvisionStatus
    step: str = ""
    recap: str = ""
    error: str | None = None
    registered: bool = False
    started_at: datetime
    finished_at: datetime | None = None

    # Докуда прочитан лог: это смещение интерфейс пришлёт следующим запросом.
    offset: int = 0
    chunk: str = ""

    # Заполнены только пока прогон жив в памяти процесса — показать пароль один раз.
    panel_password: str = ""
    # Куда идти за панелью: команда SSH-туннеля и адрес в браузере.
    tunnel: str = ""
    panel_url: str = ""

    model_config = {"from_attributes": True}
