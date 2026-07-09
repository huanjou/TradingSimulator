import asyncio

import asyncpg


async def main():
    try:
        conn = await asyncpg.connect(
            "postgresql://admin:password@localhost:5432/ledger_db"
        )
        print("Connected!")
        await conn.close()
    except Exception as e:
        print("Error:", type(e), e)


asyncio.run(main())
