"""Настройки приложения vibe_mail.

Читаются из переменных окружения и файла `.env` (через pydantic-settings).
Пароль SMTP — только здесь (SMTP_PASSWORD), в конфиг не попадает.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- SMTP (глобальный отправитель на всё приложение) ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    # --- База данных ---
    DATABASE_URL: str = "sqlite:///./vibe_mail.db"

    # --- Лимиты отправки ---
    RETRIES: int = 3
    DEFAULT_DELAY: float = 2.0

    # --- Источник конфигов ---
    # Серверов несколько и настройки у каждого свои, поэтому список живёт отдельным
    # YAML-файлом (см. servers.example.yml), а здесь — только путь к нему.
    VPN_SERVERS_FILE: str = "servers.yml"

    # --- Поднятие новых серверов (ansible) ---
    # Каталог со сценариями: site.yml, roles/, group_vars/all.yml. Лежит в репозитории
    # и едет в образ, поэтому путь относительный и совпадает в dev и в контейнере.
    # Пусто или нет site.yml — кнопка «Поднять новый сервер» выключена.
    ANSIBLE_DIR: str = "ansible"
    # Куда писать логи прогонов и одноразовые inventory. В контейнере это том /data:
    # каталог приложения принадлежит root, и писать в него процесс не может.
    PROVISION_DIR: str = "data/provision"
    # Предел на один прогон: полное обновление пакетов с перезагрузкой — это минуты,
    # но зависший плейбук не должен держать очередь вечно.
    PROVISION_TIMEOUT_MIN: int = 60
    # Кем и на каком порту будут жить поднятые серверы. Форма подставляет это, а прогон
    # получает явным `-e`. Пусто (и 0) — взять из `group_vars/all.yml` сценариев: там
    # умолчания нейтральные, потому что каталог лежит в публичном репозитории.
    PROVISION_ADMIN_USER: str = ""
    PROVISION_SSH_PORT: int = 0

    # --- CORS (фронт в dev на отдельном порту, Vite :5173) ---
    # Через запятую; пустое значение (например, пустая env-переменная) — взять умолчание.
    CORS_ORIGINS: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    """Возвращает кешированный синглтон настроек."""
    return Settings()
