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

    def _normalize_name(self, name: str) -> str:
        """内部辅助方法，用于统一处理名称的标准化逻辑。"""
        return name.strip().lower()

    async def find_or_create(self, name: str) -> Ingredient:
        """
        根据名称查找食材，如果不存在，则创建一个新的。
        这是一个原子性的操作，被 RecipeService 依赖。
        """
        # 1. 对输入名称进行标准化处理
        normalized_name = self._normalize_name(name)

        # 2. 尝试根据标准化名称查找已存在的食材
        existing_ingredient = await self.find_by_normalized_name(normalized_name)

        # 3. 如果找到了，直接返回
        if existing_ingredient:
            return existing_ingredient

        # 4. 如果没找到，则创建新的食材
        #    注意：我们同时填充了 name 和 normalized_name
        new_ingredient_data = {
            "name": name.strip(),
            "normalized_name": normalized_name
        }

        # 5. 调用基类的 create 方法来执行创建
        new_ingredient = await self.create(new_ingredient_data)

        return new_ingredient

    # =================================================================

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

