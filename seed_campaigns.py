"""Сидинг БД: создаёт 15 кампаний и ~40 фейковых получателей с конфигами.

Запуск из корня репозитория:
    pipenv run python seed_campaigns.py

Таблицы создаются через Base.metadata.create_all (на случай пустой БД).

Распределение получателей подобрано для проверки всего флоу отправки:
- у кампаний со статусом NEW — пачка PENDING (их можно запустить вручную
  через «Запустить рассылку» и наблюдать отправку);
- у IN_PROGRESS — по 1 PENDING (воркер подхватит при старте и дошлёт);
- у DONE/ERROR — завершённые/упавшие получатели (история в логе).
"""

import datetime
import random

from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    Campaign,
    CampaignStatus,
    Config,
    Recipient,
    RecipientStatus,
)
from app.db.session import SessionLocal, engine
from app.services import server_service as srv

random.seed(1234)

FAKE_NAMES: list[str] = [
    "Иван",
    "Мария",
    "Алексей",
    "Ольга",
    "Дмитрий",
    "Анна",
    "Сергей",
    "Елена",
    "Павел",
    "Юлия",
]

FAKE_DOMAINS: list[str] = ["example.com", "test.ru", "mail.org", "vibe.dev"]

FAKE_CONFIG_PREFIXES: list[str] = ["Ivanov_Ivan", "Petrova_Anna", "Sidorov_Pavel", "Root_Olga"]

# Сколько получателей и с какими статусами создаём для каждого статуса кампании.
RECIPIENT_PLAN: dict[CampaignStatus, tuple[int, list[RecipientStatus]]] = {
    CampaignStatus.NEW: (14, [RecipientStatus.PENDING]),
    CampaignStatus.IN_PROGRESS: (1, [RecipientStatus.PENDING]),
    CampaignStatus.DONE: (
        1,
        [RecipientStatus.SENT, RecipientStatus.FAILED],
    ),
    CampaignStatus.ERROR: (1, [RecipientStatus.FAILED]),
}


def _days_ago(days: int) -> datetime.datetime:
    """Возвращает naive-UTC время на N дней назад от текущего момента."""
    base = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    return base - datetime.timedelta(days=days)


def _build_recipients(status: CampaignStatus, index: int) -> list[Recipient]:
    """Фейковые получатели для кампании с учётом её статуса.

    `index` — порядковый номер кампании в SEED, чтобы у завершённых кампаний
    получатели получали разные статусы (SENT/FAILED) для разнообразия
    в логе.
    """
    count, statuses = RECIPIENT_PLAN[status]
    recipients: list[Recipient] = []

    for i in range(count):
        recipient_status = (
            statuses[index % len(statuses)] if len(statuses) > 1 else statuses[i % len(statuses)]
        )
        is_finished = recipient_status == RecipientStatus.SENT
        sent_at = _days_ago(random.randint(0, 30)) if is_finished else None
        error = (
            "Ошибка SMTP: таймаут соединения с сервером"
            if recipient_status == RecipientStatus.FAILED
            else None
        )

        prefix = random.choice(FAKE_CONFIG_PREFIXES)
        recipient = Recipient(
            email=f"user{i}@{random.choice(FAKE_DOMAINS)}",
            name=random.choice(FAKE_NAMES),
            client_name=f"{prefix}_{i}",
            status=recipient_status,
            error=error,
            sent_at=sent_at,
        )
        # Каждый номер конфига на каждом включённом сервере — как это делает импорт.
        config_count = random.randint(1, 3)
        recipient.config_count = config_count
        recipient.configs = [
            Config(seq=seq, server_key=server.key, kind=server.artifact_kind)
            for seq in range(1, config_count + 1)
            for server in srv.enabled_servers()
        ]
        recipients.append(recipient)

    return recipients


# (name, subject, body, status, created_at_days_ago)
SEED: list[tuple[str, str, str, CampaignStatus, int]] = [
    (
        "Новогодняя рассылка 2026",
        "С наступающим 2026 годом!",
        "Дорогой клиент, поздравляем вас с Новым годом и дарим скидку 20%.",
        CampaignStatus.DONE,
        210,
    ),
    (
        "Запуск нового тарифа Pro",
        "Попробуйте Vibe Pro бесплатно 14 дней",
        "Мы запустили тариф Pro с расширенной аналитикой. Активируйте прямо сейчас.",
        CampaignStatus.IN_PROGRESS,
        1,
    ),
    (
        "Опрос удовлетворённости",
        "Помогите нам стать лучше — 2 минуты вашего времени",
        "Пройдите короткий опрос и получите промокод на следующий заказ.",
        CampaignStatus.IN_PROGRESS,
        12,
    ),
    (
        "Вебинар по массовым рассылкам",
        "Регистрируйтесь на бесплатный вебинар 15 сентября",
        "Разберём лучшие практики рассылок с индивидуальными вложениями.",
        CampaignStatus.NEW,
        3,
    ),
    (
        "Восстановление корзины",
        "Вы забыли товары в корзине 🛒",
        "Ваши товары всё ещё ждут вас. Завершите оформление со скидкой 10%.",
        CampaignStatus.DONE,
        45,
    ),
    (
        "Ежемесячный дайджест — август",
        "Что нового в Vibe за август",
        "Подборка обновлений, кейсов и полезных статей за прошедший месяц.",
        CampaignStatus.DONE,
        30,
    ),
    (
        "Специальное предложение для партнёров",
        "Партнёрская программа: +15% к вознаграждению",
        "До конца месяца повышенный процент за привлечённых клиентов.",
        CampaignStatus.IN_PROGRESS,
        6,
    ),
    (
        "Техническое обслуживание API",
        "Плановые работы 1 сентября с 02:00 до 04:00",
        "Сообщаем о плановом обслуживании. Сервис будет временно недоступен.",
        CampaignStatus.DONE,
        25,
    ),
    (
        "Приглашение на закрытую вечеринку",
        "Только для клиентов Premium",
        "Приглашаем вас на вечеринку для партнёров и VIP-клиентов.",
        CampaignStatus.ERROR,
        8,
    ),
    (
        "Обновление политики конфиденциальности",
        "Важные изменения в политике конфиденциальности",
        "Ознакомьтесь с обновлёнными условиями обработки данных.",
        CampaignStatus.DONE,
        60,
    ),
    (
        "Летняя распродажа — скидки до 50%",
        "Летние скидки в приложении Vibe",
        "Успейте купить по сниженным ценам до конца сезона.",
        CampaignStatus.DONE,
        75,
    ),
    (
        "Welcome-серия: шаг 1 из 3",
        "Добро пожаловать в Vibe! Начнём с основ",
        "Краткое руководство для новых пользователей: первые шаги в сервисе.",
        CampaignStatus.IN_PROGRESS,
        2,
    ),
    (
        "Напоминание об оплате подписки",
        "Ваша подписка истекает через 3 дня",
        "Продлите подписку, чтобы не потерять накопленные данные.",
        CampaignStatus.IN_PROGRESS,
        0,
    ),
    (
        "Кейс: как мы ускорили отправку в 3 раза",
        "Инженерный разбор фоновой рассылки",
        "Рассказываем, как архитектура на FastAPI ускорила доставку писем.",
        CampaignStatus.NEW,
        18,
    ),
    (
        "Поздравление с профессиональным праздником",
        "С днём программиста!",
        "Поздравляем всех разработчиков с профессиональным праздником!",
        CampaignStatus.DONE,
        15,
    ),
]


def seed(db: Session) -> tuple[int, int]:
    Base.metadata.create_all(engine)
    campaign_count = 0
    recipient_count = 0

    for idx, (name, subject, body, status, days) in enumerate(SEED):
        campaign = Campaign(
            name=name,
            subject=subject,
            body=body,
            status=status,
            created_at=_days_ago(days),
        )
        db.add(campaign)

        for recipient in _build_recipients(status, idx):
            campaign.recipients.append(recipient)
            recipient_count += 1

        campaign_count += 1

    db.commit()
    return campaign_count, recipient_count


def main() -> None:
    db = SessionLocal()
    try:
        campaigns, recipients = seed(db)
        print(f"Создано кампаний: {campaigns}, получателей: {recipients}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
