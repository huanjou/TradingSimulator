from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# We convert PostgresDsn to string for SQLAlchemy
engine = create_async_engine(
    str(settings.POSTGRES_URL),
    echo=settings.ENV == "development",
    pool_size=10,
    max_overflow=20,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    """
    Dependency function that yields a database session.
    Automatically handles closing the session after the request finishes.
    """
    async with AsyncSessionLocal() as session:
        yield session
