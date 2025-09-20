# app/services/recipes/ingredient_service.py

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select, func

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException
from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipes.recipe import Ingredient, RecipeIngredient  # 导入 RecipeIngredient 用于检查
from app.schemas.recipes.ingredient_schemas import IngredientCreate, IngredientUpdate, IngredientRead, \
    BatchActionIngredientsPayload, IngredientMergePayload
from app.repo.crud.recipes.ingredient_repo import IngredientRepository
from app.repo.crud.common.base_repo import PageResponse
from app.services._base_service import BaseService


class IngredientService(BaseService):
    def __init__(self, factory: RepositoryFactory):
        super().__init__()
        self.factory = factory
        self.ingredient_repo: IngredientRepository = factory.get_repo_by_type(IngredientRepository)

    def _normalize_name(self, name: str) -> str:
        """内部辅助方法，用于生成标准化的名称。"""
        return name.strip().lower()

    async def get_ingredient_by_id(self, ingredient_id: UUID, view_mode: str = ViewMode.ACTIVE) -> Ingredient:
        ingredient = await self.ingredient_repo.get_by_id(ingredient_id, view_mode=view_mode)
        if not ingredient:
            raise NotFoundException("食材不存在")
        return ingredient

    async def page_list_ingredients(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any], view_mode: str
    ) -> PageResponse[IngredientRead]:
        paged_results = await self.ingredient_repo.get_paged_ingredients(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}, view_mode=view_mode
        )
        return paged_results

    async def create_ingredient(self, ingredient_in: IngredientCreate) -> Ingredient:
        """【重构】创建新食材，使用 begin_nested 事务。"""
        normalized_name = self._normalize_name(ingredient_in.name)
        if await self.ingredient_repo.find_by_normalized_name(normalized_name):
            raise AlreadyExistsException(f"已存在名为 '{ingredient_in.name}' 的食材")

        async with self.ingredient_repo.db.begin_nested():
            create_data = ingredient_in.model_dump()
            create_data["normalized_name"] = normalized_name
            new_ingredient = await self.ingredient_repo.create(create_data)

        return new_ingredient

    async def update_ingredient(self, ingredient_id: UUID, ingredient_in: IngredientUpdate) -> Ingredient:
        """【重构】更新食材，使用 begin_nested 事务。"""
        async with self.ingredient_repo.db.begin_nested():
            ingredient_to_update = await self.get_ingredient_by_id(ingredient_id)
            update_data = ingredient_in.model_dump(exclude_unset=True)
            if not update_data:
                return ingredient_to_update

            if "name" in update_data:
                new_normalized_name = self._normalize_name(update_data["name"])
                if new_normalized_name != ingredient_to_update.normalized_name:
                    existing = await self.ingredient_repo.find_by_normalized_name(new_normalized_name)
                    if existing and existing.id != ingredient_id:
                        raise AlreadyExistsException(f"更新失败，已存在名为 '{update_data['name']}' 的食材")
                    update_data["normalized_name"] = new_normalized_name

            updated_ingredient = await self.ingredient_repo.update(ingredient_to_update, update_data)

        return updated_ingredient

    async def soft_delete_ingredients(self, payload: BatchActionIngredientsPayload) -> int:
        """【重构后】高性能地批量软删除食材。"""
        ingredient_ids = list(set(payload.ingredient_ids))
        if not ingredient_ids:
            return 0

        async with self.ingredient_repo.db.begin_nested():
            # 1. 【性能优化】一次性获取所有待删除食材的使用计数
            usage_counts = await self.ingredient_repo.get_usage_counts_for_ids(ingredient_ids)

            # 2. 在内存中进行检查
            for ing_id in ingredient_ids:
                if usage_counts.get(ing_id, 0) > 0:
                    ing = await self.ingredient_repo.get_by_id(ing_id)
                    raise BusinessRuleException(
                        f"无法删除食材 '{ing.name}'，因为它正被 {usage_counts[ing_id]} 个活跃菜谱使用"
                    )

            # 3. 执行删除
            deleted_count = await self.ingredient_repo.soft_delete_by_ids(ingredient_ids)

        return deleted_count

    async def restore_ingredients(self, payload: BatchActionIngredientsPayload) -> int:
        """【新增】批量恢复食材。"""
        if not payload.ingredient_ids:
            return 0

        async with self.ingredient_repo.db.begin_nested():
            # 校验这些 ID 是否确实是已删除状态
            ingredients_to_restore = await self.ingredient_repo.get_by_ids(payload.ingredient_ids,
                                                                           view_mode=ViewMode.DELETED)
            if len(ingredients_to_restore) != len(set(payload.ingredient_ids)):
                raise NotFoundException("一个或多个要恢复的食材不存在于回收站中。")
            restored_count = await self.ingredient_repo.restore_by_ids(payload.ingredient_ids)

        return restored_count

    async def permanent_delete_ingredients(self, payload: BatchActionIngredientsPayload) -> int:
        """【重构后】更安全地批量永久删除食材（高危操作）。"""
        ingredient_ids = list(set(payload.ingredient_ids))
        if not ingredient_ids:
            return 0

        async with self.ingredient_repo.db.begin_nested():
            # 1. 确认它们都在回收站里
            ingredients_to_delete = await self.ingredient_repo.get_by_ids(ingredient_ids, view_mode=ViewMode.DELETED)
            if len(ingredients_to_delete) != len(ingredient_ids):
                raise NotFoundException("一个或多个要永久删除的食材不存在于回收站中。")

            # 2. 【安全增强】永久删除前，再次进行关联检查
            #    这里可以根据业务定义，是检查活跃菜谱，还是所有菜谱。检查活跃的更常见。
            usage_counts = await self.ingredient_repo.get_usage_counts_for_ids(ingredient_ids)
            for ing in ingredients_to_delete:
                if usage_counts.get(ing.id, 0) > 0:
                    raise BusinessRuleException(f"无法永久删除食材 '{ing.name}'，因为它仍被活跃菜谱引用")

            # 3. 执行删除
            deleted_count = await self.ingredient_repo.hard_delete_by_ids(ingredient_ids)

        return deleted_count

    async def merge_ingredients(self, payload: IngredientMergePayload) -> IngredientRead:
        """【新增】将多个源食材合并到一个目标食材。"""
        source_ids = list(set(payload.source_ingredient_ids))
        target_id = payload.target_ingredient_id

        async with self.ingredient_repo.db.begin_nested():
            if target_id in source_ids:
                raise BusinessRuleException("目标食材不能是被合并的源食材之一。")

            # 检查所有ID是否存在
            target_ingredient = await self.get_ingredient_by_id(target_id)
            source_ingredients = await self.ingredient_repo.get_by_ids(source_ids)
            if len(source_ingredients) != len(source_ids):
                raise NotFoundException("一个或多个指定的源食材ID不存在。")

            # 【重要业务逻辑】处理合并后可能在一个菜谱中出现重复食材的问题
            # 这是一个复杂问题，理想的解决方案需要检查每个菜谱，然后合并数量。
            # 为保持此方法简洁，我们暂时先接受可能产生重复行，并依赖 repo 的 merge_ingredients
            await self.ingredient_repo.merge_ingredients(source_ids, target_id)

        # 重新获取更新后的目标食材信息
        updated_target = await self.get_ingredient_by_id(target_id)
        # 获取最新的菜谱计数
        recipe_count = await self.ingredient_repo.get_recipe_count(target_id)

        dto = IngredientRead.model_validate(updated_target)
        dto.recipe_count = recipe_count
        return dto