"""ORM-модели: Campaign, Recipient, Config."""

import datetime
import enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.servers import ArtifactKind
from app.db.base import Base


def _now() -> datetime.datetime:
    """Текущее время в UTC (naive) — для полей created_at/sent_at."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


# Разделитель между базовым именем получателя и номером конфига. Без него имена с
# цифрой на конце читаются неоднозначно: `alice2` с двумя конфигами дал бы `alice21`.
CONFIG_NAME_SEPARATOR = "-"


def config_client_name(base: str, seq: int) -> str:
    """Имя клиента на панели: базовое имя получателя плюс номер конфига.

    Единственное место, где это имя собирается, — им пользуются и модель, и
    предпросмотр импорта.
    """
    return f"{base}{CONFIG_NAME_SEPARATOR}{seq}"


class CampaignStatus(enum.StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DONE_WITH_ERRORS = "done_with_errors"
    ERROR = "error"


class RecipientStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class ConfigStatus(enum.StrEnum):
    PENDING = "pending"  # имя есть, файла ещё нет
    QUEUED = "queued"  # поставлен в очередь на генерацию
    GENERATING = "generating"  # воркер взял в работу
    READY = "ready"
    FAILED = "failed"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(1024))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus), default=CampaignStatus.NEW
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    recipients: Mapped[list["Recipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class Recipient(Base):
    __tablename__ = "recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Базовое имя клиента на VPN-серверах. Само по себе на сервер не уезжает: имена
    # конфигов получаются из него нумерацией (`alice` → `alice1`, `alice2`, …).
    client_name: Mapped[str] = mapped_column(String(255))
    # Сколько конфигов заказано этому получателю. Хранится явно, а не считается по
    # `configs`: без включённых серверов конфигов нет, а количество знать надо.
    config_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[RecipientStatus] = mapped_column(
        SAEnum(RecipientStatus), default=RecipientStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="recipients")
    configs: Mapped[list["Config"]] = relationship(
        back_populates="recipient", cascade="all, delete-orphan", order_by="Config.server_key"
    )


class Config(Base):
    """Что получатель получает с одного VPN-сервера.

    У человека может быть несколько конфигов (телефон, ноутбук, роутер), и каждый из
    них заводится на каждом включённом сервере. Строка здесь — это пересечение
    «какой по счёту конфиг» × «какой сервер»: получатель с тремя конфигами и четырьмя
    серверами даёт двенадцать строк.

    Что именно лежит в строке, говорит `kind`: панели WireGuard отдают файл (`content` —
    BLOB, конфиги весят единицы килобайт, отдельной сущности под файл не заводим),
    3x-ui — ссылку подписки (`link`). Пока конфиг не сгенерирован, оба поля пусты,
    а статус показывает, на какой стадии он находится.

    Имя клиента не хранится, а выводится из базового имени получателя и `seq`
    (см. `name`): так переименование остаётся правкой в одном месте, а не разносится
    по десятку строк.
    """

    __tablename__ = "configs"
    __table_args__ = (
        # Один артефакт на пару «порядковый номер конфига — сервер».
        UniqueConstraint(
            "recipient_id", "seq", "server_key", name="uq_config_recipient_seq_server"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("recipients.id", ondelete="CASCADE"), index=True
    )
    # Порядковый номер конфига у получателя, с единицы. Он же попадает в имя клиента.
    seq: Mapped[int] = mapped_column(Integer, default=1)
    # Имя клиента на панели, когда оно НЕ выводится из базового имени и номера: так
    # подхватываются клиенты, заведённые на сервере руками под своим именем. Пусто —
    # имя обычное, производное.
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Ключ сервера из servers.yml. Строкой, а не внешним ключом: список серверов
    # живёт в конфиге, а не в БД.
    server_key: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[ArtifactKind] = mapped_column(SAEnum(ArtifactKind), default=ArtifactKind.FILE)
    status: Mapped[ConfigStatus] = mapped_column(SAEnum(ConfigStatus), default=ConfigStatus.PENDING)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    recipient: Mapped["Recipient"] = relationship(back_populates="configs")

    @property
    def name(self) -> str:
        """Имя, которое видит получатель: в имени вложения и рядом со ссылкой.

        Всегда выводится из базового имени получателя и порядкового номера — номер есть
        и у единственного конфига: иначе добавление второго потребовало бы переименовать
        первый, а в AmneziaWG переименования нет.

        На панели клиент может называться иначе (см. `panel_name`): короткие служебные
        имена вроде `adonm` человеку ничего не говорят, и показывать их незачем.
        """
        return config_client_name(self.recipient.client_name, self.seq)

    @property
    def panel_name(self) -> str:
        """Имя клиента на самой панели — им и только им оперируют адаптеры.

        Обычно совпадает с `name`. Расходится, когда клиент заведён на сервере руками
        под своим именем: переименовать его нельзя, поэтому храним как есть
        в `external_name` и ходим на панель с ним.
        """
        return self.external_name or self.name

    @property
    def is_external(self) -> bool:
        """Привязан ли конфиг к клиенту, заведённому на панели вручную."""
        return self.external_name is not None

    @property
    def is_ready(self) -> bool:
        """Есть ли то, что можно положить в письмо."""
        if self.kind is ArtifactKind.LINK:
            return bool(self.link)
        return self.content is not None

    @property
    def download_filename(self) -> str:
        """Имя файла для отдачи наружу.

        Берётся человеческое имя, а не `panel_name`: файл уходит получателю, и служебное
        сокращение с панели ему ничего не скажет. Ключ сервера обязателен — один конфиг
        заводится на нескольких WireGuard-панелях под одним именем, и без него в письме
        оказались бы два вложения с одинаковым `alice-1.conf`.
        """
        return f"{self.name}_{self.server_key}.conf"
