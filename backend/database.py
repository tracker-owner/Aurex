from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Для локального теста используем SQLite. 
# Файл arcanum.db создастся автоматически в папке backend.
DATABASE_URL = "sqlite+aiosqlite:///./arcanum.db"

# Когда будете заливать на реальный хостинг, замените строку выше на:
# DATABASE_URL = "postgresql+asyncpg://bejam26722:pazuhinNe_Valid1@localhost:5432/arcanum_db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
