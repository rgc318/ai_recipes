from app.config.settings import settings
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DatabaseError
import app.models


DATABASE_URL = settings.database.url

# 初始化数据库引擎和 Session
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 获取 DB session（依赖注入用）
async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# 初始化数据库（启动时调用）
async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
