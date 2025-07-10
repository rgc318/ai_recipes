from typing import Optional, Sequence, List
from uuid import UUID

from fastapi import Depends

from app.db.repository_factory_auto import RepositoryFactory
from app.db.get_repo_factory import get_repository_factory
from app.models.recipe import Recipe
from app.schemas.recipe_schemas import RecipeCreate, RecipeUpdate
from app.db.crud.recipe_repo import RecipeRepository


class RecipeService:
    def __init__(self, factory: RepositoryFactory = Depends(get_repository_factory)):
        self.factory = factory
        self.recipe_repo: RecipeRepository = factory.get_repo_by_type(RecipeRepository)

    async def list_recipes(self) -> Sequence[Recipe]:
        return await self.recipe_repo.get_all()

    async def list_recipes_paginated(
        self,
        page: int = 1,
        per_page: int = 10,
        search: str = "",
        order_by: str = "created_at desc",
    ) -> List[Recipe]:
        return await self.recipe_repo.list_paginated(
            page=page,
            per_page=per_page,
            search=search,
            order_by=order_by,
        )

    async def get_by_id(self, recipe_id: UUID) -> Optional[Recipe]:
        return await self.recipe_repo.get_by_id(recipe_id)

    async def create(
        self, recipe_in: RecipeCreate, created_by: Optional[UUID] = None
    ) -> Recipe:
        recipe = await self.recipe_repo.create(recipe_in)

        if created_by:
            recipe.created_by = created_by
            recipe.updated_by = created_by
            session = self.factory.get_session()
            session.add(recipe)
            await session.commit()
            await session.refresh(recipe)

        return recipe

    async def update(
        self, recipe_id: UUID, recipe_in: RecipeUpdate, updated_by: Optional[UUID] = None
    ) -> Optional[Recipe]:
        recipe = await self.recipe_repo.update(recipe_id, recipe_in)

        if recipe and updated_by:
            recipe.updated_by = updated_by
            session = self.factory.get_session()
            session.add(recipe)
            await session.commit()
            await session.refresh(recipe)

        return recipe

    async def delete(self, recipe_id: UUID, deleted_by: Optional[UUID] = None) -> bool:
        recipe = await self.recipe_repo.soft_delete(recipe_id)

        if recipe and deleted_by:
            recipe.deleted_by = deleted_by
            session = self.factory.get_session()
            session.add(recipe)
            await session.commit()
            await session.refresh(recipe)

        return recipe is not None
