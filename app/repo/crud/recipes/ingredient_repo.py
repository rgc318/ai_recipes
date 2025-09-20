# app/repo/crud/ingredient_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.query_enums import ViewMode
from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import Ingredient, RecipeIngredient, Recipe
from app.schemas.recipes.ingredient_schemas import IngredientCreate, IngredientUpdate, IngredientRead


class IngredientRepository(BaseRepository[Ingredient, IngredientCreate, IngredientUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        super().__init__(db=db, model=Ingredient, context=context)

    def _normalize_name(self, name: str) -> str:
        """内部辅助方法，用于统一处理名称的标准化逻辑。"""
        return name.strip().lower()

    async def find_or_create(self, name: str) -> Ingredient:
        """
        【重构后】根据名称查找或创建食材，增加行级锁以防止并发冲突。
        """
        normalized_name = self._normalize_name(name)
        if not normalized_name:
            raise ValueError("Ingredient name cannot be empty.")

        try:
            # 使用 with_for_update() 来锁定可能匹配的行，防止竞态条件
            stmt = select(self.model).where(self.model.normalized_name == normalized_name).with_for_update()
            result = await self.db.execute(stmt)
            return result.scalar_one()
        except NoResultFound:
            self.logger.info(f"Ingredient '{normalized_name}' not found, creating a new one.")
            new_ingredient_data = {"name": name.strip(), "normalized_name": normalized_name}
            new_ingredient = self.model(**new_ingredient_data)
            self.db.add(new_ingredient)
            await self.db.flush()
            await self.db.refresh(new_ingredient)
            return new_ingredient

    # =================================================================

    async def find_by_normalized_name(self, normalized_name: str) -> Optional[Ingredient]:
        """根据标准化名称精确查找食材。"""
        # [修改] - find_by_field 是我们在 BaseRepository 中创建的更通用的方法
        return await self.find_by_field(normalized_name, "normalized_name")

    async def get_paged_ingredients(
            self, *,
            page: int,
            per_page: int,
            filters: Dict[str, Any],
            sort_by: List[str],
            view_mode: str = ViewMode.ACTIVE.value
    ) -> PageResponse[IngredientRead]:
        """
        【重构后】获取食材的分页列表，并附带每个食材关联的活跃菜谱数量。
        完全复刻自 TagRepository 的高级模式。
        """
        # 1. 定义一个子查询，只包含活跃的菜谱
        active_recipes_subquery = select(Recipe.id).where(Recipe.is_deleted == False).subquery()

        # 2. 定义用于计数的列
        recipe_count_col = func.count(RecipeIngredient.recipe_id).label("recipe_count")

        # 3. 构建核心查询语句
        stmt = (
            select(self.model, recipe_count_col)
            .outerjoin(RecipeIngredient, self.model.id == RecipeIngredient.ingredient_id)
            # 【关键】只与活跃的菜谱进行 join，确保计数准确
            .join(active_recipes_subquery, RecipeIngredient.recipe_id == active_recipes_subquery.c.id, isouter=True)
            .group_by(self.model.id)
        )

        # 4. 将所有复杂工作委托给强大的基类 get_paged_list
        paged_response = await self.get_paged_list(
            page=page,
            per_page=per_page,
            filters=filters,
            sort_by=sort_by,
            view_mode=view_mode,
            stmt_in=stmt,
            sort_map={'recipe_count': recipe_count_col},  # 告诉基类如何排序 'recipe_count'
            return_scalars=False  # 因为我们需要返回 (Ingredient, count) 元组
        )

        # 5. 处理基类返回的元组列表，构造成最终的 DTO
        dto_items = []
        for item_orm, count in paged_response.items:
            item_dto = IngredientRead.model_validate(item_orm)
            item_dto.recipe_count = count if count is not None else 0
            dto_items.append(item_dto)

        paged_response.items = dto_items
        return paged_response

    async def merge_ingredients(self, source_ids: List[UUID], target_id: UUID) -> None:
        """
        【新增】合并食材的核心数据库操作。
        将所有对 source_ids 的引用，更新为 target_id。
        """
        if not source_ids:
            return

        # 1. 更新 RecipeIngredient 链接表
        # 注意：这里可能会导致一个菜谱中有重复的食材，这个业务逻辑问题应该在 Service 层处理
        update_stmt = (
            update(RecipeIngredient)
            .where(RecipeIngredient.ingredient_id.in_(source_ids))
            .values(ingredient_id=target_id)
        )
        await self.db.execute(update_stmt)

        # 2. 物理删除源食材记录
        await self.hard_delete_by_ids(source_ids)

    async def get_recipe_count(self, ingredient_id: UUID) -> int:
        """
        获取一个食材被多少个【活跃】菜谱使用。
        """
        # 1. 定义一个子查询，只包含活跃的菜谱
        active_recipe_subquery = select(Recipe.id).where(Recipe.is_deleted == False).subquery()

        # 2. 构建计数语句，只 join 活跃的菜谱
        count_stmt = (
            select(func.count(RecipeIngredient.recipe_id))
            .join(active_recipe_subquery, RecipeIngredient.recipe_id == active_recipe_subquery.c.id)
            .where(RecipeIngredient.ingredient_id == ingredient_id)
        )

        usage_count = await self.db.scalar(count_stmt)
        return usage_count or 0

    async def get_usage_counts_for_ids(self, ingredient_ids: List[UUID]) -> Dict[UUID, int]:
        """
        为一组食材ID，高效地批量获取它们各自被【活跃】菜谱使用的次数。
        这是 get_recipe_count 的批量版本，用于解决 N+1 性能问题。
        """
        if not ingredient_ids:
            return {}

        active_recipe_subquery = select(Recipe.id).where(Recipe.is_deleted == False).subquery()

        stmt = (
            select(
                RecipeIngredient.ingredient_id,
                func.count(RecipeIngredient.recipe_id).label("count")
            )
            .join(active_recipe_subquery, RecipeIngredient.recipe_id == active_recipe_subquery.c.id)
            .where(RecipeIngredient.ingredient_id.in_(ingredient_ids))
            .group_by(RecipeIngredient.ingredient_id)
        )

        result = await self.db.execute(stmt)
        # 将结果 [(id, count), ...] 转换为一个字典 {id: count, ...} 以便快速查找
        return {ing_id: count for ing_id, count in result.all()}
