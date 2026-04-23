from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from payment.infrastructure.config.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Генератор сессий базы данных.
    
    Обеспечивает создание асинхронной сессии SQLAlchemy, автоматический коммит
    при успешном завершении и откат (rollback) при возникновении исключения.
    Используется как зависимость (dependency) в FastAPI.

    Yields:
        AsyncGenerator[AsyncSession, None]: Асинхронная сессия БД.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
