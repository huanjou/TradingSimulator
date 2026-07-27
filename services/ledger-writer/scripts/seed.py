import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_db():
    logger.info("Nothing to seed for ledger-writer right now.")


if __name__ == "__main__":
    asyncio.run(seed_db())
