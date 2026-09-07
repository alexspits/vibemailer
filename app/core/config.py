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

    # --- CORS (фронт в dev на отдельном порту, Vite :5173) ---
    # Через запятую; пустое значение (например, пустая env-переменная) — взять умолчание.
    CORS_ORIGINS: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    """Возвращает кешированный синглтон настроек."""
    return Settings()
