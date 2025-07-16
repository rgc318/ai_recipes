# app/repositories/repository_factory_manul.py

from functools import cached_property
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any, TypeVar
from app.db.crud.user_repo import UserRepository
from app.db.crud.recipe_repo import RecipeRepository

RepoType = TypeVar("RepoType")


class RepositoryFactory:
    def __init__(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        group_id: Optional[str] = None,
    ):
        self._db = db
        self.context = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "group_id": group_id,
        }
        self._registry: dict[str, Any] = {}

    # 👇 仓库属性 + 注册（使用 cached_property 支持延迟加载和 IDE 补全）
    @cached_property
    def user(self) -> UserRepository:
        repo = UserRepository(self._db, context=self.context)
        self._registry["management"] = repo
        return repo

    @cached_property
    def recipe(self) -> RecipeRepository:
        repo = RecipeRepository(self._db, context=self.context)
        self._registry["recipe"] = repo
        return repo

    # 👇 动态按名称获取仓库
    def get_repo(self, name: str) -> Any:
        name = name.lower()
        if name not in self._registry:
            # 触发 cached_property 的初始化
            if hasattr(self, name):
                getattr(self, name)
        repo = self._registry.get(name)
        if not repo:
            raise ValueError(f"Repository '{name}' not found.")
        return repo

    # 👇 允许 factory.management.create() 这样的访问
    def __getattr__(self, item: str) -> Any:
        return self.get_repo(item)

    # 👇 通用 session 操作（支持 service 中统一提交）
    async def commit(self): await self._db.commit()
    async def rollback(self): await self._db.rollback()
    async def flush(self): await self._db.flush()
    async def refresh(self, instance): await self._db.refresh(instance)
    def get_session(self) -> AsyncSession: return self._db
