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

engine_primary = None
AsyncSessionLocalPrimary = None
if settings.POSTGRES_PRIMARY_URL:
    engine_primary = create_async_engine(
        str(settings.POSTGRES_PRIMARY_URL),
        echo=settings.ENV == "development",
        pool_size=5,
        max_overflow=10,
        future=True,
    )
    AsyncSessionLocalPrimary = async_sessionmaker(
        bind=engine_primary,
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


async def get_primary_db():
    """
    Dependency function that yields a primary database session.
    Used for strict consistency requests (like state recovery).
    """
    if not AsyncSessionLocalPrimary:
        # Fallback to replica if primary is not configured
        async with AsyncSessionLocal() as session:
            yield session
    else:
        async with AsyncSessionLocalPrimary() as session:
            yield session
