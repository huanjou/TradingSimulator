from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import auth, users
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
)

# In microservice environment behind API gateway, CORS might be handled at Gateway.
# But for safety, we can allow origins if accessed directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])


@app.on_event("startup")
async def startup_event():
    from app.db.base_class import Base
    from app.db.session import engine

    # Import all models here so they are registered with Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}
