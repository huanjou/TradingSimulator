import argparse
import asyncio
import os
import sys

from app.core.kafka import kafka_client
from app.services.admin import AdminService

async def seed_symbols(symbols_list: list[str]):
    # Start Kafka client
    await kafka_client.start()
    try:
        admin_service = AdminService(kafka_client)
        for sym in symbols_list:
            sym = sym.strip()
            if not sym:
                continue
            try:
                await admin_service.create_symbol(sym)
                print(f"Symbol '{sym}' seeded to Kafka successfully.")
            except Exception as e:
                print(f"Failed to seed '{sym}': {e}")
        
        # Give Kafka a moment to flush messages
        await asyncio.sleep(1)
    finally:
        await kafka_client.stop()

def main():
    parser = argparse.ArgumentParser(description="API Gateway CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Command: seed-symbols
    parser_seed = subparsers.add_parser("seed-symbols")
    parser_seed.add_argument("--symbols", type=str, help="Comma-separated list of symbols (or set DEFAULT_SYMBOLS env var)")

    args = parser.parse_args()

    if args.command == "seed-symbols":
        symbols_str = args.symbols or os.getenv("DEFAULT_SYMBOLS", "BTC/USD,ETH/USD,SOL/USD")
        symbols_list = symbols_str.split(",")
        asyncio.run(seed_symbols(symbols_list))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
