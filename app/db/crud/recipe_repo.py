from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, text
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud.base_repo import BaseRepository
from app.models.recipe import (
    Recipe,
    RecipeIngredient,
    Unit,
    Ingredient,
    RecipeTagLink,
)
from app.schemas.recipe_schemas import (
    RecipeCreate,
    RecipeUpdate,
    RecipeIngredientInput,
)


class RecipeRepository(BaseRepository[Recipe, RecipeCreate, RecipeUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        super().__init__(db=db, model=Recipe, context=context)

    def _base_stmt(self):
        # 只负责关联预加载
        return select(self.model).options(
            selectinload(Recipe.tags),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.unit),
        )

    async def _get_base_query(self):
        # 负责关联预加载 + 排除软删除
        return select(self.model).where(
            self.model.is_deleted == False
        ).options(
            selectinload(Recipe.tags),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.unit),
        )

    async def get_all(self) -> List[Recipe]:
        stmt = self._base_stmt()
        return await self._run_and_scalars(stmt, method="get_all")

    # async def get_by_id(self, recipe_id: UUID) -> Optional[Recipe]:
    #     stmt = self._base_stmt().where(Recipe.id == recipe_id)
    #     return await self._run_and_scalar(stmt, method="get_by_id")

    async def create(self, obj_in: RecipeCreate) -> Recipe:
        now = datetime.utcnow()
        data = obj_in.model_dump()
        recipe = Recipe(
            title=data["title"],
            description=data.get("description"),
            steps=data.get("steps"),
            created_at=now,
            updated_at=now,
        )
        self.db.add(recipe)
        await self.db.flush()  # 获取 recipe.id

        if data.get("tag_ids"):
            await self._update_recipe_tags(recipe, data["tag_ids"])
        if data.get("ingredients"):
            await self._update_recipe_ingredients(recipe, data["ingredients"])

        await self.db.commit()
        await self.db.refresh(recipe)
        return recipe

    async def update(self, recipe_id: UUID, obj_in: RecipeUpdate) -> Optional[Recipe]:
        recipe = await self.get_by_id(recipe_id)
        if not recipe:
            return None

        update_attrs = obj_in.model_dump(exclude_unset=True, exclude={"tag_ids", "ingredients"})
        for key, value in update_attrs.items():
            setattr(recipe, key, value)
        recipe.updated_at = datetime.utcnow()

        self.db.add(recipe)

        if obj_in.tag_ids is not None:
            await self._update_recipe_tags(recipe, obj_in.tag_ids)

        if obj_in.ingredients is not None:
            await self._update_recipe_ingredients(recipe, obj_in.ingredients)

        await self.db.commit()
        await self.db.refresh(recipe)
        return recipe

    async def soft_delete(self, recipe_id: UUID) -> Optional[Recipe]:
        recipe = await self.get_by_id(recipe_id)
        if not recipe:
            return None

        now = datetime.utcnow()
        recipe.is_deleted = True
        recipe.deleted_at = now
        recipe.updated_at = now

        # 自动注入操作人（如果有）
        if hasattr(recipe, "deleted_by") and self.context.get("user_id"):
            recipe.deleted_by = self.context["user_id"]

        self.db.add(recipe)
        await self.db.commit()
        await self.db.refresh(recipe)
        return recipe

    async def _update_recipe_tags(self, recipe: Recipe, tag_ids: List[UUID]):
        await self.db.execute(delete(RecipeTagLink).where(RecipeTagLink.recipe_id == recipe.id))

        if not tag_ids:
            return

        links = [
            RecipeTagLink(recipe_id=recipe.id, tag_id=tag_id)
            for tag_id in tag_ids
        ]
        self.db.add_all(links)

    async def _update_recipe_ingredients(
        self,
        recipe: Recipe,
        ingredients_data: List[RecipeIngredientInput],
    ):
        await self.db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id))

        if not ingredients_data:
            return

        recipe_ingredients = []
        for item in ingredients_data:
            ingredient_obj = await self.db.get(Ingredient, item.ingredient_id)
            unit_obj = await self.db.get(Unit, item.unit_id) if item.unit_id else None
            if ingredient_obj:
                recipe_ingredients.append(
                    RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_id=ingredient_obj.id,
                        unit_id=unit_obj.id if unit_obj else None,
                        quantity=item.quantity,
                        note=item.note,
                    )
                )

        self.db.add_all(recipe_ingredients)

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = 10,
        order_by: str = "created_at desc",
        search: str = "",
    ) -> List[Recipe]:
        stmt = await self._get_base_query()

        if search:
            stmt = stmt.where(Recipe.title.ilike(f"%{search}%"))

        if order_by:
            stmt = stmt.order_by(text(order_by))

        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _update_recipe_ingredients(
            self,
            recipe: Recipe,
            ingredients_data: List[RecipeIngredientInput],
    ):
        await self.db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id))

        if not ingredients_data:
            return

        recipe_ingredients = []
        for item in ingredients_data:
            ingredient_obj = await self.db.get(Ingredient, item.ingredient_id)
            unit_obj = await self.db.get(Unit, item.unit_id) if item.unit_id else None
            if ingredient_obj:
                recipe_ingredients.append(
                    RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_id=ingredient_obj.id,
                        unit_id=unit_obj.id if unit_obj else None,
                        quantity=item.quantity,
                        note=item.note,
                    )
                )
        self.db.add_all(recipe_ingredients)