import factory
from app.db.session import AsyncSessionLocal


class AsyncSQLAlchemyFactory(factory.alchemy.SQLAlchemyModelFactory):
    @classmethod
    async def create_async(cls, session=None, **kwargs):
        """Asynchronous creation, saves to db via the session provided or default."""
        obj = cls.build(**kwargs)
        if session is None:
            async with AsyncSessionLocal() as session:
                session.add(obj)
                await session.commit()
                await session.refresh(obj)
        else:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
        return obj
