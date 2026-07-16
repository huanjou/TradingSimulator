from app.domain.user import UserEntity
from app.models.user import User as DbUser
from app.repositories.base import BaseRepository
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository(BaseRepository[DbUser]):
    def _to_domain(self, db_obj: DbUser) -> UserEntity:
        return UserEntity(
            id=str(db_obj.id),
            email=db_obj.email,
            hashed_password=db_obj.hashed_password,
        )

    async def upsert(self, db: AsyncSession, *, obj_in: UserEntity) -> None:
        """
        Upserts a user. If user exists, do nothing (for now).
        """
        stmt = (
            insert(DbUser)
            .values(
                id=obj_in.id,
                email=obj_in.email,
                hashed_password=obj_in.hashed_password,
            )
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)

    async def upsert_bulk(self, db: AsyncSession, objects: list[dict]) -> None:
        if not objects:
            return
        stmt = insert(DbUser).values(objects).on_conflict_do_nothing()
        await db.execute(stmt)


user_repo = UserRepository(DbUser)
