"""Автоподбор клиентов панели под получателей кампании.

Люди, которым рассылаются конфиги, на панелях уже есть — заведённые руками и по-разному
названные. Искать их глазами в списке на 80 имён, да ещё на четырёх панелях, дольше, чем
завести заново, поэтому все и заводили заново. Здесь это делается за один запрос.

Панели опрашиваются **по одному разу на весь запрос**, а не на каждого получателя: у
серверов с доступом через SSH каждый такой список — отдельная команда на машине, и
подбор для тридцати человек превратился бы в сто двадцать заходов.

Сам подбор — в `client_matcher`, здесь только сбор данных и разметка занятого.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.orm import joinedload

from app.db.models import Config, Recipient
from app.schemas.suggest import (
    ClientCandidate,
    RecipientSuggestion,
    ServerSuggestion,
    SuggestResult,
)
from app.services import campaign_service as cs
from app.services import client_matcher as matcher
from app.services import server_service as srv

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.core.servers import ServerConfig

log = logging.getLogger("vibe_mail.suggest")

# Сколько кандидатов показывать по каждому серверу: дальше идёт шум, в котором выбирать
# тяжелее, чем искать руками.
MAX_CANDIDATES = 6

# Кандидат из прошлой рассылки — не догадка: этому адресу этот клиент уже доставался.
HISTORY_SOURCE = "history"
MATCH_SOURCE = "match"


def _panel_names(server: ServerConfig) -> tuple[list[str], str | None]:
    """Имена клиентов панели и текст ошибки, если она не ответила."""
    try:
        return srv.list_panel_clients(server.key), None
    except Exception as exc:  # noqa: BLE001 - недоступная панель не должна валить подбор
        # У HTTPException в str() спереди код ответа: «502: Панель…». Здесь это не
        # ответ пользователю, а строчка в интерфейсе, и код в ней только мешает.
        reason = str(getattr(exc, "detail", exc))
        log.warning("Подбор: панель %s не ответила: %s", server.key, reason)
        return [], reason


def _past_bindings(
    db: Session, campaign_id: int, emails: set[str]
) -> dict[str, set[tuple[str, str]]]:
    """Что этим адресам уже доставалось в прошлых рассылках.

    Привязки между кампаниями не наследуются: `external_name` живёт на строке конфига,
    а строка принадлежит получателю конкретной кампании. Но история в базе есть, и она
    точнее любого подбора по имени — человеку уже отдавали именно этого клиента.

    Берём `panel_name`, а не только `external_name`: если в прошлый раз конфиг не
    привязывали, человеку всё равно завели клиента под производным именем, и вернуть
    ему тот же доступ — то же самое действие.
    """
    if not emails:
        return {}

    rows = (
        db.query(Config)
        .join(Recipient, Config.recipient_id == Recipient.id)
        .options(joinedload(Config.recipient))
        .filter(Recipient.email.in_(emails), Recipient.campaign_id != campaign_id)
        .order_by(Config.id.desc())
        .all()
    )

    history: dict[str, set[tuple[str, str]]] = {}

    for config in rows:
        history.setdefault(config.recipient.email, set()).add(
            (config.server_key, config.panel_name)
        )

    return history


def _taken_names(db: Session, campaign_id: int) -> dict[tuple[str, str], str]:
    """Занятые имена кампании: (сервер, имя на панели) → почта того, кто их занял.

    Занятый клиент не исчезает из выдачи, а помечается: увидеть «уже у Иванова» полезнее,
    чем не увидеть ничего и гадать, почему человек не нашёлся.
    """
    # joinedload: дальше у каждого конфига спрашивается почта получателя, и без него
    # на кампании в 80 человек это триста отдельных запросов.
    configs = (
        db.query(Config)
        .join(Recipient, Config.recipient_id == Recipient.id)
        .options(joinedload(Config.recipient))
        .filter(Recipient.campaign_id == campaign_id)
        .all()
    )

    return {(config.server_key, config.panel_name): config.recipient.email for config in configs}


def _stop_words(server: ServerConfig) -> frozenset[str]:
    """Слова имени, которые ничего не говорят о человеке: ключ сервера и его хвосты."""
    return frozenset({server.key.lower(), *(s.lower() for s in server.name_suffixes)})


def _for_recipient(
    recipient: Recipient,
    hint: str,
    panels: list[tuple[ServerConfig, list[str], str | None]],
    taken: dict[tuple[str, str], str],
    history: set[tuple[str, str]],
) -> RecipientSuggestion:
    """Подбор по всем серверам для одного получателя."""
    # Почта — главный признак: это адрес самого человека. Базовое имя слабее, в нём
    # фамилия сокращена до буквы, поэтому оно идёт отдельным, «слабым» набором.
    strong = [term for term in (hint, recipient.email.split("@")[0]) if term.strip()]
    weak = [recipient.client_name] if recipient.client_name else []

    servers = []

    for server, names, error in panels:
        live = set(names)
        # Прошлые привязки — вперёд и только те, что на панели ещё живы: предлагать
        # привязку к исчезнувшему клиенту значит обещать то, чего не будет.
        from_history = [name for key, name in sorted(history) if key == server.key and name in live]

        found = matcher.match(strong, weak, names, _stop_words(server))
        rest = [c for c in found if c.name not in set(from_history)]

        candidates = [
            ClientCandidate(
                name=name,
                score=1.0,
                suggested=(server.key, name) not in taken,
                taken_by=taken.get((server.key, name)),
                source=HISTORY_SOURCE,
            )
            for name in from_history
        ]

        candidates += [
            ClientCandidate(
                name=candidate.name,
                score=candidate.score,
                # Занятый клиент галочку не получает: привязать его всё равно нельзя.
                suggested=candidate.suggested and (server.key, candidate.name) not in taken,
                taken_by=taken.get((server.key, candidate.name)),
                source=MATCH_SOURCE,
            )
            for candidate in rest[:MAX_CANDIDATES]
        ]

        servers.append(
            ServerSuggestion(
                server_key=server.key,
                server_title=server.title,
                candidates=candidates,
                error=error,
            )
        )

    return RecipientSuggestion(
        recipient_id=recipient.id,
        email=recipient.email,
        client_name=recipient.client_name,
        servers=servers,
    )


def suggest_clients(
    db: Session,
    campaign_id: int,
    recipient_ids: list[int] | None,
    hints: dict[str, str],
) -> SuggestResult:
    """Кандидаты в привязку для получателей кампании. Ничего не меняет."""
    campaign = cs.get_campaign(db, campaign_id)

    wanted = set(recipient_ids or [])
    recipients = [r for r in campaign.recipients if not wanted or r.id in wanted]

    if not recipients:
        return SuggestResult(recipients=[])

    panels = [(server, *_panel_names(server)) for server in srv.enabled_servers()]
    taken = _taken_names(db, campaign.id)
    history = _past_bindings(db, campaign.id, {r.email for r in recipients})

    return SuggestResult(
        recipients=[
            _for_recipient(
                recipient,
                hints.get(str(recipient.id), ""),
                panels,
                taken,
                history.get(recipient.email, set()),
            )
            for recipient in recipients
        ]
    )
