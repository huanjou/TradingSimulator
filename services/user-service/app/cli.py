import argparse
import asyncio
import os
import sys

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import User as DBUser
from app.repositories.user import UserRepository

async def create_superuser(email: str, password: str):
    max_retries = 10
    for attempt in range(max_retries):
        try:
            async with AsyncSessionLocal() as db:
                repo = UserRepository(db)
                existing_user = await repo.get_by_email(email)
                if existing_user:
                    print(f"User {email} already exists.")
                    return

                hashed_password = await get_password_hash(password)
                db_obj = DBUser(
                    email=email,
                    hashed_password=hashed_password,
                    is_active=True,
                    is_superuser=True,
                )
                await repo.create(db_obj)
                await db.commit()
                print(f"Superuser {email} created successfully.")
                return
        except Exception as e:
            if "relation \"users\" does not exist" in str(e):
                print(f"Table 'users' does not exist yet. Retrying in 2 seconds (Attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(2)
            else:
                print(f"Error creating superuser: {e}")
                raise

def main():
    parser = argparse.ArgumentParser(description="User Service CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Command: create-superuser
    parser_superuser = subparsers.add_parser("create-superuser")
    parser_superuser.add_argument("--email", type=str, help="Email of the superuser (or set ADMIN_EMAIL env var)")
    parser_superuser.add_argument("--password", type=str, help="Password of the superuser (or set ADMIN_PASSWORD env var)")

    args = parser.parse_args()

    if args.command == "create-superuser":
        email = args.email or os.getenv("ADMIN_EMAIL")
        password = args.password or os.getenv("ADMIN_PASSWORD")
        if not email or not password:
            print("Error: --email and --password are required either as arguments or environment variables.")
            sys.exit(1)
        asyncio.run(create_superuser(email, password))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
