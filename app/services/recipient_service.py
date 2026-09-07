"""Работа с получателями: валидация, добавление, готовность к отправке."""

from email.utils import parseaddr

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.constants import EMAIL_RE
from app.db.models import Campaign, Config, Recipient, RecipientStatus
from app.schemas.recipient import RecipientCreate
from app.services import server_service as srv


def validate_email(email: str) -> bool:
    """Проверка синтаксиса email."""
    return bool(EMAIL_RE.match(parseaddr(email)[1] or email))


def _normalize_email(raw: str) -> str:
    """Почта в том виде, в каком она хранится: без пробелов по краям, в нижнем регистре."""
    return raw.strip().lower()


def build_configs(seq_numbers: range | list[int]) -> list[Config]:
    """Пустые конфиги: каждый порядковый номер на каждом включённом сервере."""
    return [
        Config(seq=seq, server_key=server.key, kind=server.artifact_kind)
        for seq in seq_numbers
        for server in srv.enabled_servers()
    ]


def _build_recipient(campaign_id: int, item: RecipientCreate, email: str) -> Recipient:
    """Собирает получателя вместе с его (пока пустыми) конфигами."""
    recipient = Recipient(
        campaign_id=campaign_id,
        email=email,
        name=item.name,
        client_name=item.client_name,
        config_count=item.count,
        status=RecipientStatus.PENDING,
    )
    recipient.configs = build_configs(range(1, item.count + 1))
    return recipient


def _validate_items(
    campaign_id: int, items: list[RecipientCreate], known_emails: set[str]
) -> tuple[list[Recipient], list[str]]:
    """Проверяет пакет и собирает получателей к созданию.

    Дубликаты ловятся и по уже существующим в кампании адресам, и внутри самого пакета.
    """
    seen = set(known_emails)
    problems: list[str] = []
    to_create: list[Recipient] = []

    for idx, item in enumerate(items, start=1):
        email = _normalize_email(item.email)

        if not email or not validate_email(email):
            problems.append(f"recipients[{idx}]: некорректный адрес {email!r}")
            continue
        if not item.client_name.strip():
            problems.append(f"recipients[{idx}]: не указано имя конфига")
            continue
        if email in seen:
            problems.append(f"recipients[{idx}]: дубликат адреса {email}")
            continue

        seen.add(email)
        to_create.append(_build_recipient(campaign_id, item, email))

    return to_create, problems


def _existing_emails(db: Session, campaign_id: int) -> set[str]:
    """Адреса, уже заведённые в кампании."""
    rows = db.query(Recipient.email).filter_by(campaign_id=campaign_id).all()
    return {row[0].lower() for row in rows}


def add_recipients(db: Session, campaign_id: int, items: list[RecipientCreate]) -> list[Recipient]:
    """Добавляет получателей с валидацией.

    Почта приводится к нижнему регистру — в таком виде и сохраняется, как при импорте
    вставленного списка (`import_service`).

    Атомарно: при любой ошибке (некорректный синтаксис, дубликат в кампании или в
    пакете) ничего не создаётся, возвращается HTTPException 400 со списком проблем.
    """
    known_emails = _existing_emails(db, campaign_id)
    to_create, problems = _validate_items(campaign_id, items, known_emails)

    if problems:
        raise HTTPException(status_code=400, detail={"errors": problems})

    db.add_all(to_create)
    db.commit()
    for recipient in to_create:
        db.refresh(recipient)

    return to_create


def add_configs(
    db: Session, recipient_id: int, server_keys: list[str] | None, count: int
) -> Recipient:
    """Дозаводит получателю ещё `count` конфигов на каждом из указанных серверов.

    Номера продолжаются отдельно по каждому серверу: у человека может быть пять
    доступов на одном сервере и один на остальных — на панелях это разные клиенты, и
    сквозная нумерация заставила бы заводить лишних просто ради ровного счёта.

    `config_count` держим равным самому длинному ряду: импорт умеет только добавлять и
    берёт большее из заказанного и существующего, так что занизить его — значит на
    следующем импорте молча получить дубли.
    """
    recipient = get_recipient(db, recipient_id)
    keys = srv.resolve_keys(server_keys)
    servers = {server.key: server for server in srv.enabled_servers()}

    for key in keys:
        last = max((c.seq for c in recipient.configs if c.server_key == key), default=0)
        recipient.configs.extend(
            Config(seq=seq, server_key=key, kind=servers[key].artifact_kind)
            for seq in range(last + 1, last + 1 + count)
        )

    recipient.config_count = max(config.seq for config in recipient.configs)
    db.commit()
    db.refresh(recipient)

    return recipient


def get_recipients(
    db: Session, campaign_id: int, status: RecipientStatus | None = None
) -> list[Recipient]:
    query = db.query(Recipient).filter_by(campaign_id=campaign_id)
    if status is not None:
        query = query.filter_by(status=status)
    return query.order_by(Recipient.id).all()


def get_recipient(db: Session, recipient_id: int) -> Recipient:
    recipient = db.get(Recipient, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Получатель не найден")
    return recipient


def _recipient_problems(recipient: Recipient) -> list[str]:
    """Что мешает отправить письмо конкретному получателю."""
    if not recipient.configs:
        return [f"{recipient.email}: не заведено ни одного конфига"]

    return [
        f"{recipient.email}: конфиг {config.name} на сервере {config.server_key} "
        "ещё не сгенерирован"
        for config in recipient.configs
        if not config.is_ready
    ]


def reset_failed(db: Session, campaign_id: int) -> int:
    """Возвращает упавших получателей в очередь. Возвращает их количество.

    Воркер берёт только PENDING, поэтому упавшее письмо само уже не повторится: после
    завершения кампании такой человек остаётся без конфигов навсегда. А причины падений
    почти всегда временные — почта отвергла пачку, оборвалась сеть, — и повторить их
    нужно уметь, не трогая тех, кому письмо уже ушло.
    """
    failed = (
        db.query(Recipient).filter_by(campaign_id=campaign_id, status=RecipientStatus.FAILED).all()
    )

    for recipient in failed:
        recipient.status = RecipientStatus.PENDING
        recipient.error = None

    db.commit()

    return len(failed)


def validate_campaign_ready(db: Session, campaign: Campaign) -> list[str]:
    """Проверяет, готова ли кампания к отправке.

    Получатель должен получить полный набор: файлы уезжают вложениями, ссылки подписки
    текстом в теле, и половинчатое письмо уже не переотправить. Поэтому пока хоть один
    конфиг на любом из серверов не сгенерирован, старт запрещён. Возвращает список
    проблем; пустой список = можно отправлять.
    """
    recipients = db.query(Recipient).filter_by(campaign_id=campaign.id).all()

    problems: list[str] = [] if recipients else ["В кампании нет получателей"]

    if not srv.enabled_servers():
        problems.append("В конфиге нет ни одного включённого сервера")
    for recipient in recipients:
        problems.extend(_recipient_problems(recipient))

    return problems
