import asyncio
import logging

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

API_URL = "http://localhost/api/v1"


async def main():
    async with httpx.AsyncClient(base_url=API_URL) as client:
        logger.info("Starting database seeding...")

        # 1. Seed Symbols
        symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        for sym in symbols:
            try:
                resp = await client.post("/admin/symbols", json={"symbol": sym})
                if resp.status_code in (200, 201):
                    logger.info(f"Symbol '{sym}' seeded successfully")
                else:
                    logger.error(f"Failed to seed symbol '{sym}': {resp.text}")
            except Exception as e:
                logger.error(f"Connection error while seeding '{sym}': {e}")

        # 2. Seed Admin User
        admin_data = {"email": "admin@admin.com", "password": "admin"}
        try:
            resp = await client.post("/auth/register", json=admin_data)
            if resp.status_code in (200, 201):
                logger.info("Admin user 'admin@admin.com' created successfully")
            elif resp.status_code == 400 and "already exists" in resp.text.lower():
                logger.info("Admin user 'admin@admin.com' already exists")
            else:
                logger.error(
                    f"Failed to create admin user: {resp.status_code} - {resp.text}"
                )
        except Exception as e:
            logger.error(f"Connection error while seeding user: {e}")

        logger.info("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())
