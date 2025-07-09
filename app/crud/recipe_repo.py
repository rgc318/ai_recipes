from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.crud.base_repo import BaseRepository
from app.models.recipe import (
    Recipe,
    RecipeIngredient,
    Tag,
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
    def __init__(self):
        super().__init__(Recipe)

    async def _get_base_query(self):
        """预加载关联并排除软删除的基础查询语句"""
        return select(self.model).where(
            self.model.is_deleted == False
        ).options(
            selectinload(Recipe.tags),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.unit),
        )

    async def get_all(self, db: AsyncSession) -> List[Recipe]:
        stmt = await self._get_base_query()
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, db: AsyncSession, recipe_id: UUID) -> Optional[Recipe]:
        stmt = await self._get_base_query()
        stmt = stmt.where(Recipe.id == recipe_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj_in: RecipeCreate) -> Recipe:
        now = datetime.utcnow()
        recipe_data = obj_in.model_dump()
        recipe = Recipe(
            title=recipe_data["title"],
            description=recipe_data.get("description"),
            steps=recipe_data.get("steps"),
            created_at=now,
            updated_at=now,
        )
        db.add(recipe)
        await db.flush()  # 获取 recipe.id

        if recipe_data.get("tag_ids"):
            await self._update_recipe_tags(db, recipe, recipe_data["tag_ids"])

        if recipe_data.get("ingredients"):
            await self._update_recipe_ingredients(db, recipe, recipe_data["ingredients"])

        await db.commit()
        await db.refresh(recipe)
        return recipe  # 🔄 优化：避免额外查询

    async def update(self, db: AsyncSession, recipe_id: UUID, obj_in: RecipeUpdate) -> Optional[Recipe]:
        recipe = await self.get_by_id(db, recipe_id)
        if not recipe:
            return None

        update_attrs = obj_in.model_dump(exclude_unset=True, exclude={"tag_ids", "ingredients"})
        for key, value in update_attrs.items():
            setattr(recipe, key, value)
        recipe.updated_at = datetime.utcnow()

        db.add(recipe)

        if obj_in.tag_ids is not None:
            await self._update_recipe_tags(db, recipe, obj_in.tag_ids)

        if obj_in.ingredients is not None:
            await self._update_recipe_ingredients(db, recipe, obj_in.ingredients)

        await db.commit()
        await db.refresh(recipe)
        return recipe  # 🔄 避免重复 get_by_id

    async def soft_delete(
        self,
        db: AsyncSession,
        recipe_id: UUID,
        deleted_by: Optional[UUID] = None
    ) -> Optional[Recipe]:
        recipe = await self.get_by_id(db, recipe_id)
        if not recipe:
            return None

        now = datetime.utcnow()
        recipe.is_deleted = True
        recipe.deleted_at = now
        recipe.updated_at = now
        recipe.deleted_by = deleted_by

        db.add(recipe)
        await db.commit()
        await db.refresh(recipe)
        return recipe

    async def _update_recipe_tags(
        self, db: AsyncSession, recipe: Recipe, tag_ids: List[UUID]
    ):
        await db.execute(delete(RecipeTagLink).where(RecipeTagLink.recipe_id == recipe.id))

        if not tag_ids:
            return

        # ⚡ 优化：批量创建 tag 关联
        links = [
            RecipeTagLink(recipe_id=recipe.id, tag_id=tag_id)
            for tag_id in tag_ids
        ]
        db.add_all(links)

    async def _update_recipe_ingredients(
        self,
        db: AsyncSession,
        recipe: Recipe,
        ingredients_data: List[RecipeIngredientInput],
    ):
        await db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id))

        if not ingredients_data:
            return

        # ⚡ 批量插入优化
        recipe_ingredients = []
        for item in ingredients_data:
            ingredient_obj = await db.get(Ingredient, item.ingredient_id)
            unit_obj = await db.get(Unit, item.unit_id) if item.unit_id else None
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

        db.add_all(recipe_ingredients)

    # ✅ 可选增强：分页查询
    async def list_paginated(
        self,
        db: AsyncSession,
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

        result = await db.execute(stmt)
        return result.scalars().all()
