# app/repo/crud/recipe_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common.category_model import RecipeCategoryLink, Category
from app.models.files.file_record import FileRecord
from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import (
    Recipe,
    RecipeIngredient,
    Ingredient,  # 导入 Ingredient 用于 JOIN
    # 导入 Tag 用于 JOIN
    RecipeTagLink,
    Unit, RecipeStep, RecipeStepImageLink, RecipeGalleryLink, Tag,
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
                selectinload(Recipe.categories),  # <-- 如果您有 categories 也要加上
                selectinload(Recipe.steps).selectinload(RecipeStep.images),
                selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
                selectinload(Recipe.ingredients).selectinload(RecipeIngredient.unit),
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
            selectinload(Recipe.steps),
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
    async def set_recipe_steps(self, recipe: Recipe, steps_data: List[RecipeStepInput]) -> None:
        """【ORM模式】重新设置菜谱的所有步骤。"""
        # 1. 先删除旧的图片关联，步骤本身由 cascade='delete-orphan' 自动处理
        if recipe.steps:
            step_ids = [step.id for step in recipe.steps if step.id]
            if step_ids:
                await self.db.execute(delete(RecipeStepImageLink).where(RecipeStepImageLink.step_id.in_(step_ids)))
                await self.db.flush()

        # 2. 创建全新的 RecipeStep ORM 对象列表
        new_steps = [
            RecipeStep(
                instruction=step_in.instruction,
                duration=step_in.duration,
                step_number=i + 1,
            ) for i, step_in in enumerate(steps_data)
        ]

        # 3. 直接用新列表替换，ORM会自动处理删除旧步骤和插入新步骤
        recipe.steps = new_steps
        self.db.add(recipe)
        await self.db.flush()  # flush后, new_steps中的每个对象都会获得ID

        # 4. 为新步骤创建图片关联
        image_links_to_add = []
        for i, step_orm in enumerate(new_steps):
            step_in_data = steps_data[i]
            if step_in_data.image_ids:
                for img_id in set(step_in_data.image_ids):
                    image_links_to_add.append(
                        RecipeStepImageLink(step_id=step_orm.id, file_id=img_id)
                    )
        if image_links_to_add:
            self.db.add_all(image_links_to_add)

        await self.db.flush()

    async def set_recipe_gallery(self, recipe: Recipe, image_ids: List[UUID]) -> None:
        """【ORM模式】重新设置菜谱的图片画廊。"""
        if image_ids:
            images_map = {}
            if image_ids:
                images_result = await self.db.execute(select(FileRecord).where(FileRecord.id.in_(image_ids)))
                images_map = {img.id: img for img in images_result.scalars()}

            # 保持前端传入的顺序
            recipe.gallery_images = [images_map[img_id] for img_id in image_ids if img_id in images_map]
        else:
            recipe.gallery_images = []
        self.db.add(recipe)
        await self.db.flush()

    async def update_cover_image(self, recipe: Recipe, cover_image_id: Optional[UUID]) -> None:
        """更新菜谱的封面图片。"""
        recipe.cover_image_id = cover_image_id
        self.db.add(recipe)
        await self.db.flush()
    async def set_recipe_tags(self, recipe: Recipe, tag_ids: List[UUID]) -> None:
        """【ORM模式】重新设置菜谱的所有标签。"""
        if tag_ids:
            # Service层已校验过ID，这里直接查询
            tags_result = await self.db.execute(select(Tag).where(Tag.id.in_(tag_ids)))
            recipe.tags = tags_result.scalars().all()
        else:
            recipe.tags = [] # 如果传入空列表，则清空关系
        self.db.add(recipe)
        await self.db.flush()

    async def set_recipe_ingredients(self, recipe: Recipe, ingredients_data: List[RecipeIngredientInput]) -> None:
        """【ORM模式】重新设置菜谱的所有配料。"""
        new_ingredients = [
            RecipeIngredient(
                ingredient_id=item.ingredient,
                unit_id=item.unit_id,
                group=item.group,
                quantity=item.quantity,
                note=item.note,
            ) for item in ingredients_data
        ]
        recipe.ingredients = new_ingredients
        self.db.add(recipe)
        await self.db.flush()

    async def set_recipe_categories(self, recipe: Recipe, category_ids: List[UUID]) -> None:
        """【ORM模式】重新设置菜谱的所有分类。"""
        if category_ids:
            categories_result = await self.db.execute(select(Category).where(Category.id.in_(category_ids)))
            recipe.categories = categories_result.scalars().all()
        else:
            recipe.categories = []
        self.db.add(recipe)
        await self.db.flush()