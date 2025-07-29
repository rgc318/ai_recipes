# app/repo/crud/unit_repo.py

from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import Unit
from app.schemas.recipes.unit_schemas import UnitCreate, UnitUpdate


class UnitRepository(BaseRepository[Unit, UnitCreate, UnitUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        super().__init__(db=db, model=Unit, context=context)

    async def find_by_name(self, name: str) -> Optional[Unit]:
        """根据名称查找单位（大小写不敏感），用于防止重名。"""
        stmt = self._base_stmt().where(self.model.name.ilike(name))
        return await self._run_and_scalar(stmt, "find_by_name")

    async def get_all_units(self) -> List[Unit]:
        """【新增】获取所有未被软删除的单位，按名称排序。"""
        stmt = self._base_stmt().order_by(self.model.name.asc())
        return await self._run_and_scalars(stmt, "get_all_units")

    async def get_paged_units(
        self, *, page: int, per_page: int, filters: Dict[str, Any], sort_by: List[str]
    ) -> PageResponse[Unit]:
        """获取单位的分页列表（后台管理使用）。"""
        return await self.get_paged_list(
            page=page, per_page=per_page, filters=filters, sort_by=sort_by
        )