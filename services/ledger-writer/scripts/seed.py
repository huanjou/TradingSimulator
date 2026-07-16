import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.models.user import User
from sqlalchemy.future import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_db():
    async with AsyncSessionLocal() as session:
        # Check if users already exist
        result = await session.execute(select(User))
        users = result.scalars().all()

        if users:
            logger.info("Database is already seeded with users.")
            return

        logger.info("Seeding database...")

        # Create a default test user
        user1 = User(
            email="admin@example.com",
            hashed_password="hashed_secret_password",  # Later replace with real hashing
            is_active=True,
            is_superuser=True,
        )

        user2 = User(
            email="trader@example.com",
            hashed_password="hashed_trader_password",
            is_active=True,
            is_superuser=False,
        )

        session.add_all([user1, user2])
        await session.commit()

        logger.info("Database successfully seeded with default users.")


if __name__ == "__main__":
    asyncio.run(seed_db())
