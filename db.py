from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text

DATABASE_URL = "sqlite+aiosqlite:///./hospital.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


# 🔥 IMPORTANT: Create Tables Function
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)