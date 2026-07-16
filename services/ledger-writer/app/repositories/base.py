from typing import Any, Generic, TypeVar

from app.db.base import Base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).
        **Parameters**
        * `model`: A SQLAlchemy model class
        """
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> ModelType | None:
        result = await db.execute(select(self.model).filter(self.model.id == id))
        return result.scalars().first()

    async def create(
        self, db: AsyncSession, *, obj_in: dict[str, Any] | Base
    ) -> ModelType:
        if isinstance(obj_in, dict):
            db_obj = self.model(**obj_in)
        else:
            db_obj = obj_in  # Assume it's already a model instance if not dict

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
