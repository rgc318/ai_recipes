# app/repo/repository_factory_auto.py
import asyncio
from typing import Optional, Any, Type, TypeVar, AsyncGenerator, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from app.repo.crud.common.base_repo import BaseRepository
from app.core.request_scope import get_request_scope
# =====================
# 类型定义
# =====================
RepoType = TypeVar("RepoType", bound=BaseRepository)

# =====================
# 自定义异常
# =====================
class RepositoryNotFoundError(Exception):
    pass

class RepositoryTypeMismatchError(Exception):
    pass

# =====================
# Repository Factory
# =====================
class RepositoryFactory:
    """
    RepositoryFactory 负责管理所有 Repository 的实例化和缓存，
    并封装 Session 的事务管理功能，实现企业级解耦与可维护性。
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        group_id: Optional[str] = None,
        context: Optional[dict] = None
    ):
        self._db = db
        if context:
            self.context = context
        elif user_id or tenant_id or group_id:
            self.context = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "group_id": group_id,
            }
        else:
            self.context = get_request_scope()
        self._registry: Dict[str, BaseRepository] = {}
    # ==========
    # 通过名称获取 Repository
    # ==========
    def get_repo(self, name: str) -> BaseRepository:
        """
        根据注册名称获取 Repository 实例。
        """
        name = name.lower()
        if name not in self._registry:
            repo_cls = BaseRepository.registry.get(name)
            if not repo_cls:
                raise RepositoryNotFoundError(f"Repository '{name}' not registered.")
            instance = repo_cls(self._db, context=self.context)
            self._registry[name] = instance
        return self._registry[name]

    # ==========
    # 通过类型获取 Repository
    # ==========
    def get_repo_by_type(self, repo_type: Type[RepoType]) -> RepoType:
        """
        根据 Repository 类型获取实例。
        """
        for repo in self._registry.values():
            if isinstance(repo, repo_type):
                return repo

        # 如果未加载，则动态实例化并缓存
        for cls in BaseRepository.registry.values():
            if issubclass(cls, repo_type):
                instance = cls(self._db, context=self.context)
                key = cls.__name__.replace("Repository", "").lower()
                self._registry[key] = instance
                return instance

        raise RepositoryNotFoundError(f"Repository of type '{repo_type.__name__}' not found.")

    # ==========
    # 动态属性访问
    # ==========
    def __getattr__(self, item: str) -> Any:
        try:
            return self.get_repo(item)
        except RepositoryNotFoundError:
            raise AttributeError(f"'RepositoryFactory' object has no attribute '{item}'")

    # ==========
    # Session 操作封装
    # ==========
    async def commit(self): await self._db.commit()
    async def rollback(self): await self._db.rollback()
    async def flush(self): await self._db.flush()
    async def refresh(self, instance): await self._db.refresh(instance)
    def get_session(self) -> AsyncSession: return self._db

    # ==========
    # 事务上下文管理器
    # ==========
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[None, None]:
        try:
            yield
            await self.commit()
        except Exception:
            await self.rollback()
            raise

    # ==========
    # 异步上下文 enter/exit
    # ==========
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                await asyncio.wait_for(self.rollback(), timeout=5)
            else:
                await asyncio.wait_for(self.commit(), timeout=5)
        finally:
            await asyncio.wait_for(self._db.close(), timeout=5)

