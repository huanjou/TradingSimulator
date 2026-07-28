from uuid import UUID

from app.domain.user import User as DomainUser
from app.models.user import User as DBUser
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _to_domain(self, db_obj: DBUser) -> DomainUser:
        return DomainUser(
            id=db_obj.id,
            email=db_obj.email,
            hashed_password=db_obj.hashed_password,
            is_active=db_obj.is_active,
            is_superuser=db_obj.is_superuser,
            token_version=db_obj.token_version,
            created_at=db_obj.created_at,
            updated_at=db_obj.updated_at,
        )

    def _to_db(self, domain_obj: DomainUser) -> DBUser:
        return DBUser(
            id=domain_obj.id,
            email=domain_obj.email,
            hashed_password=domain_obj.hashed_password,
            is_active=domain_obj.is_active,
            is_superuser=domain_obj.is_superuser,
            token_version=domain_obj.token_version,
            created_at=domain_obj.created_at,
            updated_at=domain_obj.updated_at,
        )

    async def get_by_id(self, user_id: UUID | str) -> DomainUser | None:
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                return None

        db_user = await self.db.get(DBUser, user_id)
        if not db_user:
            return None
        return self._to_domain(db_user)

    async def get_by_email(self, email: str) -> DomainUser | None:
        stmt = select(DBUser).where(DBUser.email == email)
        result = await self.db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if not db_user:
            return None
        return self._to_domain(db_user)

    async def create(self, db_obj: DBUser) -> DomainUser:
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return self._to_domain(db_obj)

    async def increment_token_version(self, user_id: UUID | str) -> None:
        """Invalidate all outstanding refresh tokens for a user.

        Called on password change (and any future credential-revocation flow).
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        stmt = (
            update(DBUser)
            .where(DBUser.id == user_id)
            .values(token_version=DBUser.token_version + 1)
        )
        await self.db.execute(stmt)
        await self.db.flush()
