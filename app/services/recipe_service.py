from typing import Optional, Sequence, List
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.recipe_repo import RecipeRepository
from app.db.session import get_session
from app.models.recipe import Recipe
from app.schemas.recipe_schemas import RecipeCreate, RecipeUpdate


class RecipeService:
    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session
        self.recipe_repo = RecipeRepository()

    async def list_recipes(self) -> Sequence[Recipe]:
        """
        获取所有未删除的菜谱（含标签、配料等）。
        """
        return await self.recipe_repo.get_all(self.session)

    async def list_recipes_paginated(
        self,
        page: int = 1,
        per_page: int = 10,
        search: str = "",
        order_by: str = "created_at desc",
    ) -> List[Recipe]:
        """
        分页获取菜谱列表（可搜索/排序）。
        """
        return await self.recipe_repo.list_paginated(
            db=self.session,
            page=page,
            per_page=per_page,
            search=search,
            order_by=order_by
        )

    async def get_by_id(self, recipe_id: UUID) -> Optional[Recipe]:
        """
        获取单个菜谱详情（含标签、配料等）。
        """
        return await self.recipe_repo.get_by_id(self.session, recipe_id)

    async def create(
        self, recipe_in: RecipeCreate, created_by: Optional[UUID] = None
    ) -> Recipe:
        """
        创建新菜谱，包含标签和配料的绑定。
        """
        recipe = await self.recipe_repo.create(self.session, recipe_in)

        if created_by:
            recipe.created_by = created_by
            recipe.updated_by = created_by
            self.session.add(recipe)
            await self.session.commit()
            await self.session.refresh(recipe)

        return recipe

    async def update(
        self, recipe_id: UUID, recipe_in: RecipeUpdate, updated_by: Optional[UUID] = None
    ) -> Optional[Recipe]:
        """
        更新菜谱内容、标签与配料。
        """
        recipe = await self.recipe_repo.update(self.session, recipe_id, recipe_in)

        if recipe and updated_by:
            recipe.updated_by = updated_by
            self.session.add(recipe)
            await self.session.commit()
            await self.session.refresh(recipe)

        return recipe

    async def delete(self, recipe_id: UUID, deleted_by: Optional[UUID] = None) -> bool:
        """
        逻辑删除菜谱（软删除）。
        """
        recipe = await self.recipe_repo.soft_delete(self.session, recipe_id, deleted_by)
        return recipe is not None
