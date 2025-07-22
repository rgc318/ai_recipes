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
# 【核心修改】获取 DB session 的依赖注入函数
async def get_session() -> AsyncSession:
    """
    提供一个数据库会话，并采用明确的事务控制。
    """
    session = AsyncSessionLocal()
    try:
        yield session
        # 如果路由函数成功执行（没有抛出异常），则在最后提交所有更改。
        await session.commit()
    except Exception:
        # 如果在处理过程中发生任何异常，则回滚所有更改。
        await session.rollback()
        # 重新抛出异常，以便上层（如FastAPI的错误中间件）可以捕获和处理它。
        raise
    finally:
        # 无论成功还是失败，最终都要关闭会话，释放连接。
        await session.close()


# 初始化数据库（启动时调用）
async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
