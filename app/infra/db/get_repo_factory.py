from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager  # 1. 引入 asynccontextmanager
from typing import AsyncGenerator

from app.core.logger import logger
from app.infra.db.session import get_session, AsyncSessionLocal  # 2. 引入 AsyncSessionLocal
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.core.request_scope import get_request_scope


# --- 版本一：为 FastAPI 依赖注入系统提供的工厂获取器 ---
def get_repository_factory(
        session: AsyncSession = Depends(get_session),
        context: dict = Depends(get_request_scope),
) -> RepositoryFactory:
    """
    专为 FastAPI API 请求设计的依赖注入函数。
    它从请求上下文中自动获取 session 和 context。
    """
    logger.info(f"[get repo factory context]: {context}")
    return RepositoryFactory(
        db=session,
        user_id=context.get("user_id"),
        tenant_id=context.get("tenant_id"),
        group_id=context.get("group_id"),
        context=context,
    )


# --- 版本二：为独立脚本/后台任务提供的工厂获取器 ---
@asynccontextmanager
async def get_standalone_repository_factory(
        context: dict = None
) -> AsyncGenerator[RepositoryFactory, None]:
    """
    一个独立的、不依赖 FastAPI 请求的上下文管理器。
    用于后台任务、数据迁移脚本等场景。

    用法:
    async with get_standalone_repository_factory() as repo_factory:
        # ... 使用 repo_factory 获取 repo 并执行操作 ...
    """
    session = AsyncSessionLocal()
    try:
        # 如果没有传入上下文，则提供一个空的默认值
        final_context = context or {}

        # 在这里，我们可以自己开启一个顶级事务
        async with session.begin():
            yield RepositoryFactory(
                db=session,
                user_id=final_context.get("user_id"),
                tenant_id=final_context.get("tenant_id"),
                group_id=final_context.get("group_id"),
                context=final_context,
            )
    finally:
        # 确保会话在最后被关闭
        await session.close()
