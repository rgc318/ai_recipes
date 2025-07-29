# app/repo/crud/ingredient_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import Ingredient
from app.schemas.recipes.ingredient_schemas import IngredientCreate, IngredientUpdate


class IngredientRepository(BaseRepository[Ingredient, IngredientCreate, IngredientUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        super().__init__(db=db, model=Ingredient, context=context)

    async def find_by_normalized_name(self, normalized_name: str) -> Optional[Ingredient]:
        """
        根据标准化名称精确查找食材。
        这是 Service 层用来检查重复的核心方法，比检查原始 name 更可靠。
        """
        stmt = self._base_stmt().where(self.model.normalized_name == normalized_name)
        return await self._run_and_scalar(stmt, "find_by_normalized_name")

    async def are_ids_valid(self, ids: List[UUID]) -> bool:
        """
        高效地检查一组ID是否都存在于 ingredient 表中。
        被 RecipeService 依赖。
        """
        if not ids:
            return True

        unique_ids = set(ids)
        stmt = select(func.count(self.model.id)).where(self.model.id.in_(unique_ids))

        result = await self.db.execute(stmt)
        existing_count = result.scalar_one()

        return existing_count == len(unique_ids)

    async def get_paged_ingredients(
            self, *, page: int, per_page: int, filters: Dict[str, Any], sort_by: List[str]
    ) -> PageResponse[Ingredient]:
        """获取食材的分页列表。"""
        return await self.get_paged_list(
            page=page, per_page=per_page, filters=filters, sort_by=sort_by
        )