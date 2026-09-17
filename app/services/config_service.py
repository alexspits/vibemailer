"""Работа с конфигами получателей: постановка в очередь на генерацию, доступ к файлу."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.servers import ServerConfig
from app.db.models import Config, ConfigStatus, Recipient
from app.services import campaign_service as cs
from app.services import recipient_service as rs
from app.services import server_service as srv


def enqueue_campaign_configs(
    db: Session, campaign_id: int, server_keys: list[str] | None = None
) -> int:
    """Ставит в очередь конфиги кампании, которых ещё нет.

    `server_keys` ограничивает постановку конкретными серверами — так работают кнопки
    генерации на отдельный сервер. Пустое значение означает все включённые серверы;
    сам список приходит уже проверенным из `server_service.resolve_keys`.

    Готовые (READY) не трогаем — повторное нажатие кнопки догенерирует только
    недостающие и перезапустит упавшие. Возвращает количество поставленных в очередь.
    """
    query = (
        db.query(Config)
        .join(Recipient, Config.recipient_id == Recipient.id)
        .filter(
            Recipient.campaign_id == campaign_id,
            Config.status.in_([ConfigStatus.PENDING, ConfigStatus.FAILED]),
        )
    )

    if server_keys is not None:
        query = query.filter(Config.server_key.in_(server_keys))

    configs = query.all()

    for config in configs:
        config.status = ConfigStatus.QUEUED
        config.error = None

    db.commit()
    return len(configs)


def get_config(db: Session, config_id: int) -> Config:
    config = db.get(Config, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Конфиг не найден")
    return config


def count_by_server(db: Session, campaign_id: int) -> dict[str, dict[str, int]]:
    """Счётчики конфигов кампании в разрезе «сервер → статус → сколько».

    Нужны фронту: у каждой кнопки генерации свой прогресс, и общий счётчик по кампании
    этого не показывает.
    """
    rows = (
        db.query(Config.server_key, Config.status, Recipient.id)
        .join(Recipient, Config.recipient_id == Recipient.id)
        .filter(Recipient.campaign_id == campaign_id)
        .all()
    )

    totals: dict[str, dict[str, int]] = {}

    for server_key, status, _ in rows:
        by_status = totals.setdefault(server_key, {})
        by_status[status.value] = by_status.get(status.value, 0) + 1

    return totals


def bind_external_client(db: Session, config_id: int, external_name: str) -> Config:
    """Привязывает конфиг к клиенту, заведённому на панели вручную.

    Нужно, когда имя на сервере не ложится на схему «базовое имя + номер»: перевыпускать
    такого клиента нельзя (человек уже пользуется конфигом), а сопоставить автоматически
    не по чему. После привязки конфиг уходит в очередь — воркер заберёт его артефакт
    с панели тем же путём, что и для совпавших по имени.
    """
    config = get_config(db, config_id)
    name = external_name.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Не указано имя клиента на панели")

    if name not in srv.list_panel_clients(config.server_key):
        raise HTTPException(
            status_code=400,
            detail=f"На сервере {config.server_key} нет клиента с именем {name}",
        )

    _reject_taken_external(db, config, name)

    config.external_name = name
    config.status = ConfigStatus.QUEUED
    config.error = None
    db.commit()

    return config


def bind_new_clients(
    db: Session, recipient_id: int, server_key: str, names: list[str]
) -> Recipient:
    """Заводит получателю по конфигу на каждое имя с панели и сразу их привязывает.

    Отдельная операция, а не повторная привязка того же конфига: у конфига одно имя на
    панели, и вторая привязка затёрла бы первую. Человеку с телефоном и ноутбуком нужны
    две строки, а не одна, переписанная дважды.

    Список клиентов панели спрашиваем один раз на всю пачку: на серверах с доступом
    через SSH каждый такой запрос — отдельная команда на машине.
    """
    recipient = rs.get_recipient(db, recipient_id)
    server = srv.get_server(server_key)

    wanted = list(dict.fromkeys(name.strip() for name in names if name.strip()))

    if not wanted:
        raise HTTPException(status_code=400, detail="Не выбрано ни одного клиента")

    live = set(srv.list_panel_clients(server_key))
    missing = [name for name in wanted if name not in live]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"На сервере {server_key} нет клиентов: {', '.join(missing)}",
        )

    _reject_taken_names(db, recipient, server_key, wanted)
    _attach_names(recipient, server, wanted)

    db.commit()
    db.refresh(recipient)

    return recipient


def _attach_names(recipient: Recipient, server: ServerConfig, names: list[str]) -> None:
    """Раскладывает имена по строкам конфигов получателя. Без коммита.

    Сначала занимаются пустые строки этого сервера и только под остаток заводятся
    новые: иначе привязка к уже существующей пустой строке плодила бы рядом вторую.
    """
    free = sorted(
        (c for c in recipient.configs if c.server_key == server.key and _is_free(c)),
        key=lambda config: config.seq,
    )
    last = max((c.seq for c in recipient.configs if c.server_key == server.key), default=0)

    for offset, name in enumerate(names):
        config = free[offset] if offset < len(free) else None

        if config is None:
            config = Config(seq=last + offset - len(free) + 1, server_key=server.key)
            recipient.configs.append(config)

        config.kind = server.artifact_kind
        config.external_name = name
        config.status = ConfigStatus.QUEUED
        config.error = None

    recipient.config_count = max(config.seq for config in recipient.configs)


def _is_free(config: Config) -> bool:
    """Пустая ли строка конфига: ни привязки, ни того, что уже получено с панели."""
    return config.external_name is None and not config.is_ready


def bind_suggestions(db: Session, campaign_id: int, items: list) -> tuple[int, int]:
    """Привязывает всё отмеченное в подборе. Возвращает (привязок, получателей).

    Панели читаются по одному разу на весь запрос, проверки — до единой записи в базу:
    наполовину применённый подбор пришлось бы разбирать руками, а по именам на панелях
    непонятно, что уже привязано, а что нет.
    """
    campaign = cs.get_campaign(db, campaign_id)
    by_id = {recipient.id: recipient for recipient in campaign.recipients}

    unknown = {item.recipient_id for item in items} - set(by_id)
    if unknown:
        raise HTTPException(
            status_code=404,
            detail=f"В кампании нет получателей с id {', '.join(map(str, sorted(unknown)))}",
        )

    # Сводим запрос к виду «пара (получатель, сервер) → имена без повторов». Два
    # элемента на одну пару — не выдумка: подбор рисует чипы по серверам, и один и тот
    # же клиент может попасть в отметки дважды. Без сведения проверка «занят» ничего не
    # заметила бы (она смотрит в базу, а первая привязка ещё не записана), и человек
    # получил бы один и тот же доступ двумя вложениями.
    merged = _merge_items(items)

    servers = {key: srv.get_server(key) for _, key in merged}
    live = {key: set(srv.list_panel_clients(key)) for key in servers}

    _reject_unknown_names(merged, live)
    _reject_duplicate_names(merged, by_id)

    for (recipient_id, server_key), names in merged.items():
        recipient = by_id[recipient_id]

        _reject_taken_names(db, recipient, server_key, names)
        _attach_names(recipient, servers[server_key], names)

    db.commit()

    return sum(len(names) for names in merged.values()), len({rid for rid, _ in merged})


def _merge_items(items: list) -> dict[tuple[int, str], list[str]]:
    """Пары «получатель и сервер» с очищенными именами без повторов."""
    merged: dict[tuple[int, str], list[str]] = {}

    for item in items:
        names = merged.setdefault((item.recipient_id, item.server_key), [])
        names.extend(
            name.strip() for name in item.names if name.strip() and name.strip() not in names
        )

    return {key: names for key, names in merged.items() if names}


def _reject_unknown_names(merged: dict[tuple[int, str], list[str]], live: dict) -> None:
    """Отказ, если отмеченного клиента на панели уже нет: список мог устареть."""
    missing = {
        (server_key, name)
        for (_, server_key), names in merged.items()
        for name in names
        if name not in live[server_key]
    }

    if missing:
        listed = ", ".join(f"{key}: {name}" for key, name in sorted(missing))
        raise HTTPException(
            status_code=400,
            detail=f"Этих клиентов на панелях больше нет: {listed}. Повторите подбор.",
        )


def _reject_duplicate_names(merged: dict[tuple[int, str], list[str]], by_id: dict) -> None:
    """Отказ, если один клиент отмечен сразу у двоих.

    Подбор вполне может предложить `lisa` обеим Елизаветам, и заметить это глазами в
    длинном списке трудно. Молча отдать один доступ двоим — худший исход.
    """
    seen: dict[tuple[str, str], int] = {}

    for (recipient_id, server_key), names in merged.items():
        for name in names:
            owner = seen.setdefault((server_key, name), recipient_id)

            if owner != recipient_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Клиент {name} на сервере {server_key} отмечен сразу у "
                        f"{by_id[owner].email} и {by_id[recipient_id].email}"
                    ),
                )


def _reject_taken_names(
    db: Session, recipient: Recipient, server_key: str, names: list[str]
) -> None:
    """То же правило, что и у одиночной привязки, но сразу для пачки имён.

    Свои же конфиги здесь тоже соперники: привязать один и тот же клиент дважды одному
    человеку — это два письма с одним и тем же доступом.
    """
    rivals = (
        db.query(Config)
        .join(Recipient, Config.recipient_id == Recipient.id)
        .filter(
            Config.server_key == server_key,
            Recipient.campaign_id == recipient.campaign_id,
        )
        .all()
    )
    taken = {config.panel_name: config for config in rivals}

    for name in names:
        rival = taken.get(name)
        if rival is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Клиент {name} на сервере {server_key} уже занят "
                    f"получателем {rival.recipient.email}"
                ),
            )


def _reject_taken_external(db: Session, config: Config, name: str) -> None:
    """Один клиент панели — одному получателю кампании: иначе двое получат один доступ.

    Сравнивать только `external_name` мало: имя может быть занято и конфигом, у которого
    оно выводится из базового имени получателя. Поэтому сверяемся с `panel_name` всех
    конфигов этого сервера — их немного, и SQL так всё равно не спросишь.

    Смотрим в пределах кампании, а не по всей базе: один и тот же человек в новой
    рассылке — это тот же клиент на панели, и запрещать его повторную привязку значило
    бы запретить вторую рассылку тем же людям.
    """
    rivals = (
        db.query(Config)
        .join(Recipient, Config.recipient_id == Recipient.id)
        .filter(
            Config.server_key == config.server_key,
            Config.id != config.id,
            Recipient.campaign_id == config.recipient.campaign_id,
        )
        .all()
    )

    taken = next((c for c in rivals if c.panel_name == name), None)

    if taken is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Клиент {name} на сервере {config.server_key} уже занят "
                f"получателем {taken.recipient.email}"
            ),
        )


def unbind_external_client(db: Session, config_id: int) -> Recipient:
    """Снимает привязку, а лишнюю строку конфига убирает совсем.

    На сервер человеку полагается одна строка; всё, что сверх неё, появилось только
    под конкретного клиента панели. После отвязки такая строка не нужна: оставленная
    пустой, она при следующей генерации заведёт на панели лишнего клиента.

    Единственную строку сохраняем и просто очищаем — она и есть «конфиг на этом
    сервере», без неё человек останется без доступа.

    Артефакт сбрасывается в обоих случаях: он принадлежал чужому клиенту, и
    оставлять его под производным именем было бы враньём.
    """
    config = get_config(db, config_id)
    recipient = config.recipient
    same_server = [c for c in recipient.configs if c.server_key == config.server_key]

    if len(same_server) > 1:
        removed_id, server_key = config.id, config.server_key
        db.delete(config)
        db.flush()
        _renumber(recipient, server_key, removed_id)
    else:
        config.external_name = None
        config.status = ConfigStatus.PENDING
        _clear_artifact(config)

    db.commit()
    db.refresh(recipient)

    return recipient


def delete_config(db: Session, config_id: int) -> Recipient:
    """Удаляет строку конфига. Клиента на панели не трогает — только запись у нас."""
    config = get_config(db, config_id)
    recipient = config.recipient
    server_key = config.server_key

    removed_id = config.id
    db.delete(config)
    db.flush()
    _renumber(recipient, server_key, removed_id)
    db.commit()
    db.refresh(recipient)

    return recipient


def _renumber(recipient: Recipient, server_key: str, removed_id: int | None = None) -> None:
    """Возвращает номерам конфигов сервера сплошной ряд 1..N после удаления строки.

    Номер видит получатель — он в имени вложения (`ivan-i-3_ru.conf`), — и дырка в
    ряду выглядит потерянным файлом.

    Но перенумеровать можно не всегда. `seq` попадает в имя клиента на панели
    (`Config.name`), а клиента там никто не переименовывает — в AmneziaWG этого и не
    умеют. Сдвинуть номер у строки, которая уже привязана или уже получила конфиг,
    значит начать называть чужого пира: содержимое останется от `ivan-i-3`, а зваться
    будет `ivan-i-2`, и следующая генерация пойдёт на панель за другим клиентом.
    Поэтому ряд поправляем, только если на этом сервере все строки ещё пустые —
    обычный случай «добавил лишних и тут же убрал».

    `removed_id` — строка, которую только что отдали в `db.delete()`: из коллекции
    получателя она пропадёт лишь после обновления сессии, а до того считается живой.
    """
    survivors = [
        config
        for config in recipient.configs
        if config.server_key == server_key and config.id != removed_id
    ]

    if all(_is_free(config) for config in survivors):
        for number, config in enumerate(sorted(survivors, key=lambda c: c.seq), start=1):
            config.seq = number

    alive = [config for config in recipient.configs if config.id != removed_id]
    recipient.config_count = max((config.seq for config in alive), default=1)


def _clear_artifact(config: Config) -> None:
    """Забывает всё, что было получено с панели: файл, ссылку, размер, время."""
    config.filename = None
    config.content = None
    config.link = None
    config.size = 0
    config.error = None
    config.generated_at = None
