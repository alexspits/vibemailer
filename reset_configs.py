"""Сброс сгенерированных конфигов кампании в PENDING — чтобы перевыпустить их заново.

Нужен, когда в базе лежат конфиги, полученные не от тех панелей: например, кампанию
прогнали на заглушке (`panel: fake`), а потом вписали боевые доступы. Кнопка
«Сгенерировать» такие не тронет — она догоняет только PENDING и FAILED, а READY
считает готовыми. Без сброса получатель получит файл от заглушки.

    pipenv run python reset_configs.py 16          # вся кампания
    pipenv run python reset_configs.py 16 --server ru de2

Привязки (`external_name`) сохраняются: сбрасывается только результат генерации.
"""

from __future__ import annotations

import argparse

from app.db.models import Config, ConfigStatus, Recipient
from app.db.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campaign_id", type=int, help="id кампании")
    parser.add_argument("--server", nargs="*", default=None, help="только эти ключи серверов")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = (
            db.query(Config)
            .join(Recipient, Config.recipient_id == Recipient.id)
            .filter(Recipient.campaign_id == args.campaign_id)
        )
        if args.server:
            query = query.filter(Config.server_key.in_(args.server))

        configs = query.all()
        for config in configs:
            config.status = ConfigStatus.PENDING
            config.filename = None
            config.content = None
            config.link = None
            config.size = 0
            config.error = None
            config.generated_at = None

        db.commit()
        print(f"Сброшено конфигов: {len(configs)}. Привязки сохранены.")
        print("Дальше — кнопка «Сгенерировать» в карточке кампании.")

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
