import asyncio
import logging
import sys
from app.core.kafka import KafkaApp
from app.domain.engine import MatchingEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main():
    engine = MatchingEngine()
    app = KafkaApp(engine)
    
    logger.info("Starting Trading Engine...")
    try:
        await app.start()
    except asyncio.CancelledError:
        logger.info("Trading Engine cancelled")
    except KeyboardInterrupt:
        logger.info("Trading Engine interrupted by user")
    finally:
        logger.info("Trading Engine stopped")

if __name__ == "__main__":
    asyncio.run(main())
