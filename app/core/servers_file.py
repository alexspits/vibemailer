"""Запись `servers.yml` — единственное место, где этот файл меняется.

Читается он обычным pyyaml'ом (`load_servers`), а правится round-trip парсером ruamel:
больше половины файла — комментарии, которыми он документирует сам себя, и полная
перезапись из разобранной модели стёрла бы их на первом же переключателе в интерфейсе.
Round-trip меняет ровно те строки, которые просили, остальное оставляя байт в байт.

Пишем строго на место (`open(path, "w")`), а не во временный файл с подменой: в
контейнере этот путь — bind-mount одного файла, и `os.replace` на нём падает с EBUSY.
Плата за это — окно, в котором файл записан наполовину, поэтому перед записью рядом
кладётся копия `.bak`, а после записи результат перечитывается: испорченный servers.yml
означает потерянные доступы ко всем панелям сразу.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from app.core.servers import load_servers

# Куда `enabled` встаёт у сервера, где его ещё нет: сразу после key и title, а не в
# конец блока, где он потерялся бы среди доступов.
_ENABLED_POSITION = 2


log = logging.getLogger("vibe_mail.servers_file")


class ServersFileError(Exception):
    """Файл серверов не удалось прочитать или записать."""


def set_enabled(path: str, key: str, enabled: bool) -> None:
    """Включает или выключает сервер, не трогая остальные его настройки."""
    doc = _load(path)
    _, item = _locate(doc, key)

    if "enabled" in item:
        item["enabled"] = enabled
    else:
        item.insert(min(_ENABLED_POSITION, len(item)), "enabled", enabled)

    _write(path, doc)


def append_server(path: str, data: dict[str, Any]) -> None:
    """Дописывает сервер в конец списка. Файла может не быть — тогда он создаётся."""
    doc = _load(path)
    doc["servers"].append(data)
    _write(path, doc)


def remove_server(path: str, key: str) -> None:
    """Убирает сервер из файла вместе с его блоком."""
    doc = _load(path)
    index, _ = _locate(doc, key)
    del doc["servers"][index]
    _write(path, doc)


def _yaml() -> YAML:
    """Парсер и сериализатор с отступами как в `servers.example.yml`.

    Настройки влияют только на то, что дописывается: у разобранных узлов ruamel
    сохраняет исходное оформление. `width` задран, иначе длинный `base_url` или ссылка
    подписки переносятся на вторую строку.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    return yaml


def _load(path: str) -> CommentedMap:
    """Читает файл целиком, сохраняя комментарии. Нет файла — пустой список серверов."""
    file_path = Path(path).expanduser()

    if not file_path.is_file():
        return CommentedMap({"servers": CommentedSeq()})

    try:
        doc = _yaml().load(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ServersFileError(f"{file_path} не разобрать: {exc}") from exc

    if doc is None:
        doc = CommentedMap()

    if not isinstance(doc, dict):
        raise ServersFileError(f"В {file_path} ожидался словарь с ключом servers")

    if doc.get("servers") is None:
        doc["servers"] = CommentedSeq()

    return doc


def _locate(doc: CommentedMap, key: str) -> tuple[int, CommentedMap]:
    """Индекс и блок сервера по ключу."""
    for index, item in enumerate(doc["servers"]):
        if isinstance(item, dict) and item.get("key") == key:
            return index, item

    raise ServersFileError(f"Сервера {key} в файле нет")


def _write(path: str, doc: CommentedMap) -> None:
    """Записывает файл на место, оставив рядом копию прежнего.

    Результат сразу перечитывается тем же кодом, которым файл читает приложение: если
    после правки он не разбирается или не проходит валидацию, откатываемся на прежнее
    содержимое — лучше отказ в интерфейсе, чем панель без доступов.
    """
    file_path = Path(path).expanduser()
    previous = file_path.read_text(encoding="utf-8") if file_path.is_file() else None

    if previous is not None:
        _backup(file_path)

    with file_path.open("w", encoding="utf-8") as fh:
        _yaml().dump(doc, fh)

    try:
        load_servers(path)
    except Exception as exc:
        if previous is not None:
            file_path.write_text(previous, encoding="utf-8")
        raise ServersFileError(f"Правка сломала {file_path}, изменения отменены: {exc}") from exc


def _backup(file_path: Path) -> None:
    """Кладёт копию прежнего файла рядом. Не вышло — только предупреждение в лог.

    В контейнере каталог с приложением принадлежит root, а процесс работает от
    обычного пользователя: сам файл примонтирован и доступен на запись, а создать
    рядом с ним копию нельзя. Отказываться из-за этого от правки незачем — копия
    страхует от прерванной записи, а не от неверного содержимого (за него отвечает
    перечитывание ниже).

    Копируем `copy2`, а не пишем текст заново: внутри пароли от панелей, и права
    должны приехать те же, что у исходного файла, а не выданные по umask.
    """
    try:
        shutil.copy2(file_path, file_path.with_suffix(file_path.suffix + ".bak"))
    except OSError as exc:
        log.warning("Копию %s рядом положить не удалось: %s", file_path.name, exc)
