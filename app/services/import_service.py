"""Разбор вставленного из таблицы списка получателей.

Единственное место, где живёт парсинг: и предпросмотр, и импорт ходят сюда.

Формат — от двух до четырёх колонок, разделённых табом: имя конфига, почта,
необязательное количество и необязательные привязки к клиентам, уже заведённым на
панелях вручную (`ru:adonm`, через запятую можно несколько). Именно это Google Sheets
кладёт в буфер при копировании диапазона ячеек; хвостовых колонок может не быть вовсе —
тогда конфиг один и привязок нет.

Ключ сервера в привязке указывается явно: короткие служебные имена живут не на всех
панелях, а угадывать, где именно, значило бы ходить на них прямо во время разбора —
и ронять импорт, когда сервер недоступен.

Базовое имя у получателя одно, а сами конфиги нумеруются от него: `alice` и количество
3 дают `alice1`, `alice2`, `alice3`, и каждое имя заводится на каждом включённом
сервере. Номер есть всегда, даже у единственного конфига: иначе добавление второго
потребовало бы переименовать первый, а в AmneziaWG переименования нет.

Две строки с одной почтой и разными базовыми именами — противоречие: первая выигрывает,
вторая уезжает в проблемы. Повтор той же почты с тем же именем безвреден, количество в
таком случае берётся наибольшее.

Одно и то же имя у разных почт тоже отсекается: имя клиента на панели глобально, и два
получателя с базой `alice` дали бы `alice-1` дважды — второй упал бы уже на генерации
с «клиент уже есть». Ловим это на импорте, где ошибку видно сразу и списком. Проверяются
оба источника: и сама вставка, и получатели, уже заведённые в кампании.

Количество трактуется как «сколько должно стать», а не «сколько добавить»: повторный
импорт того же списка ничего не меняет, а увеличенное число доводит получателя до него.
Уменьшенное игнорируется — удалять уже заведённых на панелях клиентов импорт не вправе.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Config, ConfigStatus, Recipient, RecipientStatus, config_client_name
from app.schemas.import_recipients import (
    ImportGroup,
    ImportPreview,
    ImportResult,
    ImportRowProblem,
)
from app.services import server_service as srv
from app.services.recipient_service import validate_email

# Невидимые символы, которые приезжают вместе со вставкой из таблиц и ломают
# проверку адреса: неразрывный пробел, zero-width space, BOM.
_INVISIBLE = str.maketrans({"\u00a0": " ", "\u200b": "", "\ufeff": ""})

# Колонок может быть две (имя и почта) или три (плюс количество конфигов).
_MIN_COLUMNS = 2
_MAX_COLUMNS = 4
DEFAULT_COUNT = 1

# Привязка вида «ключ_сервера:имя_на_панели», несколько — через запятую.
_BINDING_SEPARATOR = ","
_BINDING_DELIMITER = ":"

# К какому по счёту конфигу цепляется привязка из импорта. Служебное имя у человека
# одно, поэтому цепляем к первому; остальные конфиги получают производные имена.
BOUND_SEQ = 1


@dataclass
class ParsedGroup:
    """Получатель, его базовое имя и сколько конфигов ему нужно.

    Почта уже приведена к нижнему регистру — в таком виде она и уходит в БД.
    """

    email: str
    client_name: str
    count: int = 1
    # Ключ сервера → имя клиента на его панели, заведённого вручную.
    bindings: dict[str, str] = field(default_factory=dict)
    # Строка вставки, где получатель встретился впервые: нужна, чтобы отчитаться о
    # конфликте имени с уже заведённым получателем.
    line: int = 0
    raw: str = ""


@dataclass
class ParsedRow:
    """Успешно разобранная строка вставки."""

    client_name: str
    email: str
    count: int
    bindings: dict[str, str] = field(default_factory=dict)


@dataclass
class _GroupOutcome:
    """Что случилось с одной группой при импорте — для подсчёта итогов."""

    is_created: bool
    is_updated: bool
    created_configs: int


# ---------------------------------------------------------------------- #
# Разбор текста
# ---------------------------------------------------------------------- #


def _normalize_text(text: str) -> str:
    """Приводит переводы строк к \\n и вычищает невидимые символы из таблиц."""
    return text.replace("\r\n", "\n").replace("\r", "\n").translate(_INVISIBLE)


def _parse_line(lineno: int, raw_line: str) -> ParsedRow | ImportRowProblem | None:
    """Разбирает одну строку вставки.

    `None` — пустая строка (пропускаем молча), `ImportRowProblem` — строку принять нельзя,
    иначе `ParsedRow` с именем клиента и почтой в нижнем регистре.
    """
    if not raw_line.strip():
        return None

    raw = raw_line.strip()
    cells = [cell.strip() for cell in raw_line.split("\t")]

    if not _MIN_COLUMNS <= len(cells) <= _MAX_COLUMNS:
        return ImportRowProblem(
            line=lineno,
            raw=raw,
            reason=(
                "ожидались от двух до четырёх колонок через таб: имя конфига, почта, "
                "необязательное количество и необязательные привязки вида «ru:adonm»"
            ),
        )

    client_name, email = cells[0], cells[1].lower()
    raw_count = cells[2] if len(cells) > 2 else ""
    raw_bindings = cells[3] if len(cells) > 3 else ""

    count = _parse_count(raw_count)
    bindings = _parse_bindings(raw_bindings)

    reason = _field_problem(client_name, email, raw_count, count)
    if reason is None and bindings is None:
        reason = (
            f"привязку {raw_bindings!r} не разобрать: ожидается «ключ_сервера:имя», "
            f"несколько — через запятую; известные серверы: {', '.join(srv.enabled_keys())}"
        )

    if reason is not None:
        return ImportRowProblem(line=lineno, raw=raw, reason=reason)

    return ParsedRow(client_name=client_name, email=email, count=count, bindings=bindings)


def _parse_bindings(raw: str) -> dict[str, str] | None:
    """Разбирает четвёртую колонку: `ru:adonm` либо несколько через запятую.

    Пусто — привязок нет. Мусор или неизвестный сервер — None, строка уйдёт в проблемы.
    """
    if not raw:
        return {}

    bindings: dict[str, str] = {}
    enabled = set(srv.enabled_keys())

    for chunk in raw.split(_BINDING_SEPARATOR):
        server_key, delimiter, panel_name = chunk.strip().partition(_BINDING_DELIMITER)
        server_key, panel_name = server_key.strip(), panel_name.strip()

        if not delimiter or not server_key or not panel_name:
            return None
        if server_key not in enabled or server_key in bindings:
            return None

        bindings[server_key] = panel_name

    return bindings


def _field_problem(client_name: str, email: str, raw_count: str, count: int | None) -> str | None:
    """Что не так с разобранными полями строки; None — всё в порядке."""
    if not client_name:
        return "не указано имя конфига"
    if not email:
        return "не указана почта"
    if not validate_email(email):
        return f"некорректная почта {email}"
    if count is None:
        return f"количество конфигов должно быть целым числом больше нуля, а не {raw_count!r}"

    return None


def _parse_count(raw: str) -> int | None:
    """Количество конфигов из третьей колонки. Пусто — один, мусор — None."""
    if not raw:
        return DEFAULT_COUNT

    try:
        count = int(raw)
    except ValueError:
        return None

    return count if count > 0 else None


@dataclass
class _Grouping:
    """Разобранные строки: получатели по почте и занятые имена."""

    by_email: dict[str, ParsedGroup] = field(default_factory=dict)
    # Имя конфига → почта, которая его заняла. Имя на панели глобально, поэтому
    # второй претендент на него — ошибка, а не второй конфиг.
    by_name: dict[str, str] = field(default_factory=dict)
    # (сервер, имя на панели) → почта: один клиент панели — одному получателю.
    by_binding: dict[tuple[str, str], str] = field(default_factory=dict)


def _add_row(
    grouping: _Grouping,
    row: ParsedRow,
    lineno: int,
    raw: str,
) -> ImportRowProblem | None:
    """Добавляет разобранную строку в группы. Возвращает проблему, если она есть."""
    known = grouping.by_email.get(row.email)

    if known is not None:
        if known.client_name == row.client_name:
            # Тот же человек с тем же именем — дубль строки. Количество берём наибольшее:
            # так «alice 2» и «alice 3» во вставке дают три конфига, а не два.
            known.count = max(known.count, row.count)
            return None

        return ImportRowProblem(
            line=lineno,
            raw=raw,
            reason=(
                f"почта {row.email} уже идёт с именем {known.client_name}: "
                "имя клиента у получателя может быть только одно"
            ),
        )

    owner = grouping.by_name.get(row.client_name)
    if owner is not None:
        return ImportRowProblem(
            line=lineno,
            raw=raw,
            reason=(
                f"имя {row.client_name} уже занято почтой {owner}: "
                "имя клиента на сервере должно быть уникальным"
            ),
        )

    conflict = next(
        (
            (key, name)
            for key, name in row.bindings.items()
            if grouping.by_binding.get((key, name), row.email) != row.email
        ),
        None,
    )

    if conflict is not None:
        key, name = conflict
        return ImportRowProblem(
            line=lineno,
            raw=raw,
            reason=(
                f"клиент {name} на сервере {key} уже привязан к {grouping.by_binding[(key, name)]}"
            ),
        )

    grouping.by_email[row.email] = ParsedGroup(
        email=row.email,
        client_name=row.client_name,
        count=row.count,
        bindings=row.bindings,
        line=lineno,
        raw=raw,
    )
    grouping.by_name[row.client_name] = row.email
    for key, name in row.bindings.items():
        grouping.by_binding[(key, name)] = row.email

    return None


def parse_recipients_text(text: str) -> tuple[list[ParsedGroup], list[ImportRowProblem]]:
    """Разбирает вставленный текст в пары «почта → имя клиента» и список проблем.

    Почта приводится к нижнему регистру, поэтому строки, отличающиеся только регистром
    адреса, попадают в одну группу (и в одно письмо).

    Проблемная строка не импортируется, но и не блокирует остальные: возвращается
    отдельным списком с номером строки, исходным текстом и причиной.
    """
    grouping = _Grouping()
    problems: list[ImportRowProblem] = []

    for lineno, raw_line in enumerate(_normalize_text(text).split("\n"), start=1):
        row = _parse_line(lineno, raw_line)

        if row is None:
            continue
        if isinstance(row, ImportRowProblem):
            problems.append(row)
            continue

        problem = _add_row(grouping, row, lineno, raw_line.strip())
        if problem is not None:
            problems.append(problem)

    return list(grouping.by_email.values()), problems


# ---------------------------------------------------------------------- #
# Предпросмотр и импорт
# ---------------------------------------------------------------------- #


def _get_existing_recipients(db: Session, campaign_id: int) -> dict[str, Recipient]:
    """Получатели кампании по нормализованной почте."""
    recipients = db.query(Recipient).filter_by(campaign_id=campaign_id).all()
    return {r.email.lower(): r for r in recipients}


def _target_count(group: ParsedGroup, recipient: Recipient | None) -> int:
    """Сколько конфигов должно стать у получателя.

    Уменьшить количество импорт не может: клиенты уже заведены на панелях, и удалять
    их молча нельзя. Поэтому берётся большее из заказанного и существующего.
    """
    existing = recipient.config_count if recipient else 0
    return max(group.count, existing)


def _missing_pairs(recipient: Recipient | None, target: int) -> list[tuple[int, str]]:
    """Пары «номер конфига — сервер», которых у получателя ещё нет.

    Так одним механизмом закрываются оба случая: человеку добавили конфигов, и в
    `servers.yml` добавили сервер — недостающее дозаводится при повторном импорте.
    """
    known = (
        {(config.seq, config.server_key) for config in recipient.configs} if recipient else set()
    )

    return [
        (seq, key)
        for seq in range(1, target + 1)
        for key in srv.enabled_keys()
        if (seq, key) not in known
    ]


def _reject_taken_names(
    groups: list[ParsedGroup], existing: dict[str, Recipient]
) -> tuple[list[ParsedGroup], list[ImportRowProblem]]:
    """Отсеивает группы, чьё базовое имя занято другим получателем кампании.

    Внутри одной вставки такие конфликты уже поймал `_add_row`; здесь ловится второй
    источник — получатели, заведённые прошлыми импортами.
    """
    taken = {r.client_name: r.email for r in existing.values()}
    taken_panel = {
        (config.server_key, config.panel_name): recipient.email
        for recipient in existing.values()
        for config in recipient.configs
    }
    accepted: list[ParsedGroup] = []
    problems: list[ImportRowProblem] = []

    for group in groups:
        binding_problem = _binding_problem(group, taken_panel)

        if binding_problem is not None:
            problems.append(binding_problem)
            continue

        owner = taken.get(group.client_name)

        if owner is not None and owner != group.email:
            problems.append(
                ImportRowProblem(
                    line=group.line,
                    raw=group.raw,
                    reason=(
                        f"имя {group.client_name} уже занято получателем {owner} "
                        "в этой кампании: имя клиента на сервере должно быть уникальным"
                    ),
                )
            )
            continue

        accepted.append(group)

    return accepted, problems


def _binding_problem(
    group: ParsedGroup, taken_panel: dict[tuple[str, str], str]
) -> ImportRowProblem | None:
    """Занят ли кто-то из клиентов панели другим получателем этой кампании."""
    for key, name in group.bindings.items():
        owner = taken_panel.get((key, name))

        if owner is not None and owner != group.email:
            return ImportRowProblem(
                line=group.line,
                raw=group.raw,
                reason=f"клиент {name} на сервере {key} уже привязан к получателю {owner}",
            )

    return None


def _build_preview_group(group: ParsedGroup, recipient: Recipient | None) -> ImportGroup:
    """Одна строка предпросмотра: что реально появится у этого получателя."""
    target = _target_count(group, recipient)
    pairs = _missing_pairs(recipient, target)
    base_name = recipient.client_name if recipient else group.client_name

    return ImportGroup(
        email=group.email,
        client_name=group.client_name,
        existing_client_name=recipient.client_name if recipient else None,
        is_existing=recipient is not None,
        count=target,
        existing_count=recipient.config_count if recipient else 0,
        new_configs=len(pairs),
        servers=sorted({key for _, key in pairs}),
        new_names=[config_client_name(base_name, seq) for seq in sorted({seq for seq, _ in pairs})],
        bindings=group.bindings,
    )


def build_preview(db: Session, campaign_id: int, text: str) -> ImportPreview:
    """Показывает, что получится при импорте. Ничего не пишет в БД.

    У уже заведённого получателя имя клиента не меняется — в `existing_client_name`
    видно, какое останется.
    """
    groups, problems = parse_recipients_text(text)
    existing = _get_existing_recipients(db, campaign_id)

    groups, taken_problems = _reject_taken_names(groups, existing)
    problems.extend(taken_problems)

    preview_groups = [_build_preview_group(group, existing.get(group.email)) for group in groups]

    return ImportPreview(
        groups=preview_groups,
        problems=problems,
        total_rows=len(preview_groups) + len(problems),
        total_recipients=sum(not g.is_existing for g in preview_groups),
        total_configs=sum(g.new_configs for g in preview_groups),
    )


def _apply_group(
    db: Session, campaign_id: int, group: ParsedGroup, existing: dict[str, Recipient]
) -> _GroupOutcome:
    """Заводит получателя (если нужно) и дописывает недостающие конфиги."""
    recipient = existing.get(group.email)
    is_created = recipient is None
    target = _target_count(group, recipient)
    missing = _missing_pairs(recipient, target)

    if recipient is None:
        recipient = Recipient(
            campaign_id=campaign_id,
            email=group.email,
            client_name=group.client_name,
            config_count=target,
            status=RecipientStatus.PENDING,
        )
        db.add(recipient)
    else:
        # Базовое имя у существующего получателя не трогаем — под ним уже заведены
        # клиенты на панелях. Меняется только количество, и только в большую сторону.
        recipient.config_count = target

    servers = {server.key: server for server in srv.enabled_servers()}
    recipient.configs.extend(
        Config(seq=seq, server_key=key, kind=servers[key].artifact_kind) for seq, key in missing
    )

    _apply_bindings(recipient, group.bindings)

    return _GroupOutcome(
        is_created=is_created,
        is_updated=bool(missing) and not is_created,
        created_configs=len(missing),
    )


def _apply_bindings(recipient: Recipient, bindings: dict[str, str]) -> None:
    """Цепляет конфиги получателя к клиентам, заведённым на панелях вручную.

    Привязка ложится на первый конфиг (`BOUND_SEQ`): служебное имя у человека одно,
    остальные конфиги получают производные имена. Генерацию здесь не запускаем — это
    делает кнопка на странице кампании.
    """
    for server_key, panel_name in bindings.items():
        config = next(
            (c for c in recipient.configs if c.seq == BOUND_SEQ and c.server_key == server_key),
            None,
        )

        if config is None or config.external_name == panel_name:
            continue

        config.external_name = panel_name

        # Артефакт, если он был, принадлежал прежнему имени — он больше не наш.
        if config.status is ConfigStatus.READY:
            config.status = ConfigStatus.PENDING
            config.filename = None
            config.content = None
            config.link = None
            config.size = 0
            config.generated_at = None


def import_recipients(db: Session, campaign_id: int, text: str) -> ImportResult:
    """Импортирует разобранные строки в кампанию.

    Импорт частичный: валидные строки сохраняются, проблемные возвращаются списком.
    Если почта уже есть в кампании, базовое имя остаётся прежним, а дозаводится только
    недостающее — новые номера конфигов и новые серверы. Поэтому повторный импорт того
    же списка ничего не меняет, а увеличенное количество или добавленный в `servers.yml`
    сервер подхватываются импортом.
    """
    groups, problems = parse_recipients_text(text)
    existing = _get_existing_recipients(db, campaign_id)

    groups, taken_problems = _reject_taken_names(groups, existing)
    problems.extend(taken_problems)

    outcomes = [_apply_group(db, campaign_id, group, existing) for group in groups]
    db.commit()

    return ImportResult(
        created_recipients=sum(o.is_created for o in outcomes),
        updated_recipients=sum(o.is_updated for o in outcomes),
        created_configs=sum(o.created_configs for o in outcomes),
        problems=problems,
    )
