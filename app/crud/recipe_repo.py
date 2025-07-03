from datetime import datetime, timezone
from typing import Sequence, Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import delete

# 确保导入了所有关联模型
from app.models.recipe import (
    Recipe,
    RecipeIngredient,
    Tag,
    Unit,
    Ingredient,
    RecipeTagLink,
)

# 确保导入了 Pydantic 输入模型
from app.schemas.recipe_schemas import RecipeCreate, RecipeUpdate, RecipeIngredientInput


class RecipeCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_recipe_with_relations_stmt(self, recipe_id: Optional[UUID] = None):
        """
        创建一个带有预加载关系的基础查询语句。
        方便在多个获取方法中复用。
        """
        stmt = select(Recipe).where(Recipe.is_deleted == False)
        if recipe_id:
            stmt = stmt.where(Recipe.id == recipe_id)

        stmt = stmt.options(
            selectinload(Recipe.tags),  # 预加载 Tag 关系
            # 嵌套加载 RecipeIngredient 及其关联的 Ingredient 和 Unit
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.unit),
        )
        return stmt

    async def get_all(self) -> Sequence[Recipe]:
        """
        获取所有未删除的菜谱，并预加载其标签和配料。
        """
        stmt = await self._get_recipe_with_relations_stmt()
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, recipe_id: UUID) -> Optional[Recipe]:
        """
        根据 ID 获取单个菜谱，并预加载其标签和配料。
        """
        stmt = await self._get_recipe_with_relations_stmt(recipe_id=recipe_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # --- 核心修改在这里：将 recipe 参数类型改为 RecipeCreate ---
    async def create(self, recipe_data: RecipeCreate) -> Recipe:
        """
        创建一个新菜谱，并处理其标签和配料关联。
        接收 RecipeCreate Pydantic 模型作为输入。
        """
        now = datetime.utcnow
        recipe = Recipe(
            title=recipe_data.title,
            description=recipe_data.description,
            steps=recipe_data.steps,
            created_at=now,
            updated_at=now,
            # id 会由 default_factory 自动生成
        )
        self.session.add(recipe)
        await self.session.flush()  # 执行 SQL 语句以获取 recipe.id，但不提交事务

        # 处理标签关联
        if recipe_data.tag_ids:
            await self._update_recipe_tags(recipe, recipe_data.tag_ids)

        # 处理配料关联
        if recipe_data.ingredients:
            await self._update_recipe_ingredients(recipe, recipe_data.ingredients)

        await self.session.commit()
        # 返回一个带有预加载关系的对象
        return await self.get_by_id(recipe.id)

    # --- update 方法也需要修改其参数类型，以接收 RecipeUpdate Pydantic 模型 ---
    async def update(self, recipe_id: UUID, updates_data: RecipeUpdate) -> Optional[Recipe]:
        """
        更新现有菜谱的基本信息、标签和配料关联。
        接收 RecipeUpdate Pydantic 模型作为输入。
        """
        recipe = await self.get_by_id(recipe_id)
        if not recipe:
            return None  # 如果菜谱不存在或已被软删除

        # 更新基本属性
        # 使用 model_dump(exclude_unset=True) 确保只更新传入的字段
        update_attrs = updates_data.model_dump(exclude_unset=True, exclude={"tag_ids", "ingredients"})
        for key, value in update_attrs.items():
            setattr(recipe, key, value)

        # recipe.updated_at = datetime.utcnow
        self.session.add(recipe)  # 将修改后的对象标记为脏，以便保存

        # 处理标签更新
        # 注意：这里检查 updates_data.tag_ids 是否为 None，而不是简单的 if updates_data.tag_ids
        # 因为如果传入空列表[]，我们希望清空标签；如果没传None，则保持不变。
        if updates_data.tag_ids is not None:
            await self._update_recipe_tags(recipe, updates_data.tag_ids)

        # 处理配料更新
        if updates_data.ingredients is not None:
            await self._update_recipe_ingredients(recipe, updates_data.ingredients)

        await self.session.commit()
        # 返回一个带有预加载关系的对象
        return await self.get_by_id(recipe.id)

    async def soft_delete(self, recipe_id: UUID, deleted_by: Optional[UUID] = None) -> Optional[Recipe]:
        """
        软删除一个菜谱。
        """
        recipe = await self.get_by_id(recipe_id)
        if not recipe:
            return None

        now = datetime.utcnow
        recipe.is_deleted = True
        recipe.deleted_at = now
        recipe.updated_at = now
        recipe.deleted_by = deleted_by
        self.session.add(recipe)
        await self.session.commit()
        await self.session.refresh(recipe)  # 刷新以获取更新后的状态
        return recipe

    # --- 辅助方法用于处理关系更新 ---

    async def _update_recipe_tags(self, recipe: Recipe, tag_ids: List[UUID]):
        """
        更新菜谱的标签关联。
        删除所有旧链接，然后创建新链接。
        """
        # 清除现有链接
        await self.session.execute(
            delete(RecipeTagLink).where(RecipeTagLink.recipe_id == recipe.id)
        )
        # 添加新链接
        for tag_id in tag_ids:
            tag_obj = await self.session.get(Tag, tag_id)
            if tag_obj:
                link = RecipeTagLink(recipe_id=recipe.id, tag_id=tag_obj.id)
                self.session.add(link)
            else:
                print(f"警告：标签 ID '{tag_id}' 未找到，跳过关联。")  # 警告或抛出错误

    async def _update_recipe_ingredients(self, recipe: Recipe, ingredients_data: List[RecipeIngredientInput]):
        """
        更新菜谱的配料关联。
        删除所有旧配料记录，然后创建新记录。
        """
        # 清除现有配料记录
        await self.session.execute(
            delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
        )
        # 添加新配料记录
        for item_data in ingredients_data:
            ingredient_obj = await self.session.get(Ingredient, item_data.ingredient_id)
            unit_obj = None
            if item_data.unit_id:
                unit_obj = await self.session.get(Unit, item_data.unit_id)

            if ingredient_obj:
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient_obj.id,
                    unit_id=unit_obj.id if unit_obj else None,
                    quantity=item_data.quantity,
                    note=item_data.note
                )
                self.session.add(recipe_ingredient)
            else:
                print(f"警告：食材 ID '{item_data.ingredient_id}' 未找到，跳过关联。")  # 警告或抛出错误