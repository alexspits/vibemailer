"""Дописывание колонок, появившихся после создания базы.

Alembic не подключён: таблицы создаёт `Base.metadata.create_all`, а существующие он не
меняет. Обычно этого хватает — после правки моделей база пересоздаётся (`make remake_db`).
Но в боевой базе живут выданные конфиги и привязки к клиентам панелей, которых на самих
панелях никто не переименует: пересоздать её — значит потерять связь с ними.

Поэтому колонки, добавленные к существующим таблицам, дописываются здесь: SQLite умеет
`ALTER TABLE ... ADD COLUMN`, и для «новое поле со значением по умолчанию» этого
достаточно. Всё, что сложнее (переименование, смена типа, перенос данных), сюда не
поместится — тогда и появится Alembic.
"""

import logging

from sqlalchemy import Engine, inspect, text

log = logging.getLogger("vibe_mail.migrate")

# Таблица → колонка → тип в SQL. Только добавление: значение у существующих строк
# остаётся NULL, и код обязан считать NULL осмысленным.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "campaigns": {"servers": "JSON"},
}


def add_missing_columns(engine: Engine) -> None:
    """Дописывает недостающие колонки в уже существующие таблицы."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in tables:
                continue

            existing = {column["name"] for column in inspector.get_columns(table)}

            for name, sql_type in columns.items():
                if name in existing:
                    continue

                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
                log.info("В таблицу %s добавлена колонка %s", table, name)
