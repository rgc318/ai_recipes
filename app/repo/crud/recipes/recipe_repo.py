# app/repo/crud/recipe_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import (
    Recipe,
    RecipeIngredient,
    Ingredient,  # 导入 Ingredient 用于 JOIN
    # 导入 Tag 用于 JOIN
    RecipeTagLink,
    Unit, RecipeStep, RecipeStepImageLink, RecipeGalleryLink,
)
from app.schemas.recipes.recipe_schemas import RecipeCreate, RecipeUpdate, RecipeIngredientInput, RecipeStepInput


class RecipeRepository(BaseRepository[Recipe, RecipeCreate, RecipeUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        """
        初始化菜谱仓库。
        """
        super().__init__(db=db, model=Recipe, context=context)

    # ==========================
    # 核心查询方法
    # ==========================

    async def get_by_id_with_details(self, recipe_id: UUID) -> Optional[Recipe]:
        stmt = (
            self._base_stmt()
            .where(self.model.id == recipe_id)
            .options(
                selectinload(Recipe.cover_image), # 预加载封面图
                selectinload(Recipe.gallery_images), # 预加载画廊
                selectinload(Recipe.tags),
                selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
                selectinload(Recipe.ingredients).selectinload(RecipeIngredient.unit),
                selectinload(Recipe.steps).selectinload(RecipeStep.images), # 预加载步骤及其图片
            )
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_paged_recipes(
            self, *, page: int, per_page: int, filters: Dict[str, Any], sort_by: List[str]
    ) -> PageResponse[Recipe]:
        """
        获取菜谱的分页列表，支持动态过滤和排序。
        此方法负责处理 Recipe 特有的过滤逻辑（如按标签、食材），
        然后调用通用的父类方法完成查询。
        """
        # 1. 开始一个基础查询语句 (已包含软删除过滤)
        stmt = self._base_stmt()

        # 2. 【预处理】处理 Recipe 特有的过滤逻辑
        # 按标签ID列表过滤
        if "tag_ids__in" in filters:
            tag_ids = filters.pop("tag_ids__in")
            if tag_ids:
                stmt = (
                    stmt.join(RecipeTagLink)
                    .where(RecipeTagLink.tag_id.in_(tag_ids))
                    .distinct()
                )

        # 按食材ID列表过滤
        if "ingredient_ids__in" in filters:
            ingredient_ids = filters.pop("ingredient_ids__in")
            if ingredient_ids:
                stmt = (
                    stmt.join(RecipeIngredient)
                    .where(RecipeIngredient.ingredient_id.in_(ingredient_ids))
                    .distinct()
                )

        # 3. 定义需要“预加载”的关联数据
        eager_loading_options = [
            selectinload(Recipe.cover_image),  # 【更新】
            selectinload(Recipe.tags),
            selectinload(Recipe.gallery_images),  # <-- 添加这一行
            selectinload(Recipe.categories),     # <-- 如果您有 categories 也要加上
            selectinload(Recipe.steps),  # 预加载步骤，但不加载步骤的图片(列表页通常不需要)
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.unit),
        ]

        # 4. 调用父类的、完全通用的分页方法，并传入预处理过的参数
        return await self.get_paged_list(
            page=page,
            per_page=per_page,
            filters=filters,  # 此处 filters 已被处理过
            sort_by=sort_by,
            eager_loads=eager_loading_options,
            stmt_in=stmt,  # 传入我们已经附加了 JOIN 的查询语句
        )

    # ==========================
    # 关联关系更新方法 (由 Service 层在事务中调用)
    # ==========================
    async def set_recipe_steps(self, recipe_id: UUID, steps_data: List[RecipeStepInput]) -> None:
        """【优化版】重新设置一个菜谱的所有步骤，采用批量操作以提升性能。"""
        await self.db.execute(delete(RecipeStep).where(RecipeStep.recipe_id == recipe_id))
        await self.db.flush()

        if not steps_data:
            return

        # --- 第一轮：批量创建所有 Step 对象 ---
        new_steps_map = {}  # 用一个字典来保存新创建的 step 和它对应的输入数据
        for i, step_in in enumerate(steps_data):
            step = RecipeStep(
                recipe_id=recipe_id,
                step_number=i + 1,
                instruction=step_in.instruction
            )
            self.db.add(step)
            new_steps_map[step] = step_in  # 建立 ORM 对象和输入 DTO 的映射

        # --- 一次性 Flush ---
        # 这一步会执行所有 INSERT 语句，并为所有 new_steps 对象填充数据库生成的 ID
        await self.db.flush()

        # --- 第二轮：批量创建所有图片关联 ---
        image_links_to_add = []
        for step_orm, step_in_data in new_steps_map.items():
            if step_in_data.image_ids:
                for img_id in set(step_in_data.image_ids):
                    image_links_to_add.append(
                        RecipeStepImageLink(step_id=step_orm.id, file_id=img_id)
                    )

        if image_links_to_add:
            self.db.add_all(image_links_to_add)

        await self.db.flush()

    async def set_recipe_gallery(self, recipe_id: UUID, image_ids: List[UUID]) -> None:
        """【新增】重新设置菜谱的图片画廊。"""
        await self.db.execute(delete(RecipeGalleryLink).where(RecipeGalleryLink.recipe_id == recipe_id))
        if image_ids:
            links = [
                RecipeGalleryLink(recipe_id=recipe_id, file_id=img_id, display_order=i)
                for i, img_id in enumerate(image_ids)
            ]
            self.db.add_all(links)
        await self.db.flush()

    async def update_cover_image(self, recipe: Recipe, cover_image_id: Optional[UUID]) -> None:
        """【新增】更新菜谱的封面图片。"""
        recipe.cover_image_id = cover_image_id
        self.db.add(recipe)
        await self.db.flush()
    async def set_recipe_tags(self, recipe_id: UUID, tag_ids: List[UUID]) -> None:
        """
        【原子化操作】重新设置一个菜谱的所有标签。
        采用“先删后增”策略。此方法不提交事务。
        """
        # 1. 删除现有所有关联
        await self.db.execute(
            delete(RecipeTagLink).where(RecipeTagLink.recipe_id == recipe_id)
        )

        # 2. 如果提供了新的标签ID，则批量插入新关联
        if tag_ids:
            # 使用 set 去重，防止意外传入重复ID
            unique_tag_ids = set(tag_ids)
            links = [
                RecipeTagLink(recipe_id=recipe_id, tag_id=tag_id)
                for tag_id in unique_tag_ids
            ]
            self.db.add_all(links)

        # 刷新 session，但不提交
        await self.db.flush()

    async def set_recipe_ingredients(
            self, recipe_id: UUID, ingredients_data: List[RecipeIngredientInput]
    ) -> None:
        """
        【高性能】重新设置一个菜谱的所有配料。
        采用“先删后增”策略，并优化了查询性能。此方法不提交事务。
        """
        # 1. 删除现有所有配料记录
        await self.db.execute(
            delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
        )
        await self.db.flush()  # 确保删除先生效

        if not ingredients_data:
            return

        # 2. 【性能优化】一次性获取所有需要的 Ingredient 和 Unit 对象
        ingredient_ids = {item.ingredient_id for item in ingredients_data}
        unit_ids = {item.unit_id for item in ingredients_data if item.unit_id}

        # 批量获取食材对象，并存入字典以供快速查找
        ing_stmt = select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
        ing_result = await self.db.execute(ing_stmt)
        ingredients_map = {ing.id: ing for ing in ing_result.scalars()}

        # 批量获取单位对象
        units_map = {}
        if unit_ids:
            unit_stmt = select(Unit).where(Unit.id.in_(unit_ids))
            unit_result = await self.db.execute(unit_stmt)
            units_map = {unit.id: unit for unit in unit_result.scalars()}

        # 3. 构建新的 RecipeIngredient 对象列表
        new_recipe_ingredients = []
        for item in ingredients_data:
            # 校验 ingredient_id 是否有效（在已获取的 map 中）
            if item.ingredient_id in ingredients_map:
                new_recipe_ingredients.append(
                    RecipeIngredient(
                        recipe_id=recipe_id,
                        ingredient_id=item.ingredient_id,
                        # 校验 unit_id 是否有效
                        unit_id=item.unit_id if item.unit_id in units_map else None,
                        quantity=item.quantity,
                        note=item.note,
                    )
                )

        # 4. 批量添加到 session
        if new_recipe_ingredients:
            self.db.add_all(new_recipe_ingredients)

        # 刷新 session，但不提交
        await self.db.flush()