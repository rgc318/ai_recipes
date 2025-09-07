# app/repo/crud/recipe_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import delete, select, insert, update
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
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
                joinedload(Recipe.cover_image),
                selectinload(Recipe.gallery_images), # 预加载画廊
                selectinload(Recipe.tags),
                selectinload(Recipe.categories).selectinload(Category.parent),
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
            joinedload(Recipe.cover_image),
            selectinload(Recipe.tags),
            selectinload(Recipe.gallery_images),  # <-- 添加这一行
            selectinload(Recipe.categories).selectinload(Category.parent),
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

        if 'tags' not in recipe.__dict__:
            recipe.tags = []

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

    # ==========================
    # ▼▼▼ 核心新增：精细化的图片画廊管理方法 ▼▼▼
    # ==========================
    async def add_gallery_images(self, recipe: Recipe, file_record_ids: List[UUID]) -> None:
        """
        【新增】为菜谱的画廊【增量添加】一批新的图片关联。
        此方法不影响已有的画廊图片。
        """
        if not file_record_ids:
            return
        # 构建需要插入到 recipe_gallery_link 中间表的数据
        links_to_add = [
            {"recipe_id": recipe.id, "file_id": image_id}
            for image_id in file_record_ids
        ]
        # 使用 SQLAlchemy Core 的 insert 语句，执行高效的批量插入
        stmt = insert(RecipeGalleryLink).values(links_to_add)
        await self.db.execute(stmt)
        await self.db.flush()
    async def remove_gallery_images(self, recipe: Recipe, image_record_ids: List[UUID]) -> None:
        """
        【新增】从菜谱的画廊中【批量删除】指定的图片关联。
        """
        if not image_record_ids:
            return
        # 直接删除中间表中的关联记录
        stmt = (
            delete(RecipeGalleryLink)
            .where(
                RecipeGalleryLink.recipe_id == recipe.id,
                RecipeGalleryLink.file_id.in_(image_record_ids)
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()
    async def replace_gallery_image_link(
            self,
            recipe: Recipe,
            old_image_record_id: UUID,
            new_image_record_id: UUID
    ) -> None:
        """
        【新增】在菜谱画廊中，将一个旧的图片关联替换为一个新的图片关联。
        """
        # 使用 update 语句，精确地更新中间表中的一条记录
        stmt = (
            update(RecipeGalleryLink)
            .where(
                RecipeGalleryLink.recipe_id == recipe.id,
                RecipeGalleryLink.file_id == old_image_record_id
            )
            .values(file_id=new_image_record_id)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        # 作为一个健壮性检查，可以确认是否真的有一行被更新了
        if result.rowcount == 0:
            raise NotFoundException("The image to be replaced is not associated with this recipe.")

    async def add_step_images(self, step_id: UUID, file_record_ids: List[UUID]) -> None:
        """为菜谱步骤【增量添加】一批新的图片关联。"""
        if not file_record_ids:
            return
        links_to_add = [
            {"step_id": step_id, "file_id": image_id}
            for image_id in file_record_ids
        ]
        stmt = insert(RecipeStepImageLink).values(links_to_add)
        await self.db.execute(stmt)
        await self.db.flush()

    async def remove_step_images(self, step_id: UUID, image_record_ids: List[UUID]) -> None:
        """从菜谱步骤中【批量删除】指定的图片关联。"""
        if not image_record_ids:
            return
        stmt = (
            delete(RecipeStepImageLink)
            .where(
                RecipeStepImageLink.step_id == step_id,
                RecipeStepImageLink.file_id.in_(image_record_ids)
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def replace_step_image_link(
            self,
            step_id: UUID,
            old_image_record_id: UUID,
            new_image_record_id: UUID
    ) -> None:
        """在菜谱步骤中，将一个旧的图片关联替换为一个新的图片关联。"""
        stmt = (
            update(RecipeStepImageLink)
            .where(
                RecipeStepImageLink.step_id == step_id,
                RecipeStepImageLink.file_id == old_image_record_id
            )
            .values(file_id=new_image_record_id)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        if result.rowcount == 0:
            raise NotFoundException("The step image to be replaced is not associated with this step.")

    # ▲▲▲ 新增结束 ▲▲▲