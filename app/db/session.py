"""Движок SQLAlchemy и фабрика сессий.

Одна БД (SQLite) используется и из HTTP-запросов, и из фонового воркера
в разных потоках, поэтому для SQLite отключаем check_same_thread.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args, future=True)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(connection, _record) -> None:
        """Включает внешние ключи: в SQLite они по умолчанию выключены.

        Без этого `ondelete="CASCADE"` в моделях — просто украшение, и каскад работает
        только когда удаляют через ORM. Прямой DELETE (например, из служебного скрипта)
        оставлял бы получателей без кампании и конфиги без получателя.
        """
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db():
    """Dependency для FastAPI: сессия на время запроса, затем закрытие."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
