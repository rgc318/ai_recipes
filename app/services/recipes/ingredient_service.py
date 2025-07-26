# app/services/recipes/ingredient_service.py

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select, func

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipe import Ingredient, RecipeIngredient  # 导入 RecipeIngredient 用于检查
from app.schemas.recipes.ingredient_schemas import IngredientCreate, IngredientUpdate, IngredientRead
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

    async def get_ingredient_by_id(self, ingredient_id: UUID) -> Ingredient:
        """获取单个食材，未找到则抛出业务异常。"""
        ingredient = await self.ingredient_repo.get_by_id(ingredient_id)
        if not ingredient:
            raise NotFoundException("食材不存在")
        return ingredient

    async def page_list_ingredients(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any]
    ) -> PageResponse[IngredientRead]:
        """获取食材分页列表，并转换为 DTO。"""
        paged_ingredients_orm = await self.ingredient_repo.get_paged_ingredients(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}
        )
        paged_ingredients_orm.items = [IngredientRead.model_validate(item) for item in paged_ingredients_orm.items]
        return paged_ingredients_orm

    async def create_ingredient(self, ingredient_in: IngredientCreate) -> Ingredient:
        """【事务性】创建新食材，并进行标准化和重名校验。"""
        # 业务规则：根据标准化名称检查重复
        normalized_name = self._normalize_name(ingredient_in.name)
        if await self.ingredient_repo.find_by_normalized_name(normalized_name):
            raise AlreadyExistsException(f"已存在名为 '{ingredient_in.name}' 的食材")

        try:
            # 准备创建数据，注入标准化名称
            create_data = ingredient_in.model_dump()
            create_data["normalized_name"] = normalized_name

            new_ingredient = await self.ingredient_repo.create(create_data)
            await self.ingredient_repo.commit()
            return new_ingredient
        except Exception as e:
            self.logger.error(f"创建食材失败: {e}")
            await self.ingredient_repo.rollback()
            raise e

    async def update_ingredient(self, ingredient_id: UUID, ingredient_in: IngredientUpdate) -> Ingredient:
        """【事务性】更新食材，并进行标准化和重名校验。"""
        ingredient_to_update = await self.get_ingredient_by_id(ingredient_id)
        update_data = ingredient_in.model_dump(exclude_unset=True)

        if not update_data:
            return ingredient_to_update

        # 业务规则：如果名称被修改，需要重新标准化并检查新名称是否与其它食材冲突
        if "name" in update_data:
            new_normalized_name = self._normalize_name(update_data["name"])
            if new_normalized_name != ingredient_to_update.normalized_name:
                existing = await self.ingredient_repo.find_by_normalized_name(new_normalized_name)
                if existing and existing.id != ingredient_id:
                    raise AlreadyExistsException(f"更新失败，已存在名为 '{update_data['name']}' 的食材")
            update_data["normalized_name"] = new_normalized_name

        try:
            updated_ingredient = await self.ingredient_repo.update(ingredient_to_update, update_data)
            await self.ingredient_repo.commit()
            return updated_ingredient
        except Exception as e:
            self.logger.error(f"更新食材 {ingredient_id} 失败: {e}")
            await self.ingredient_repo.rollback()
            raise e

    async def delete_ingredient(self, ingredient_id: UUID) -> None:
        """【事务性】删除食材，并进行使用情况检查。"""
        ingredient_to_delete = await self.get_ingredient_by_id(ingredient_id)

        # 业务规则：不允许删除正在被任何菜谱使用的食材
        count_stmt = select(func.count(RecipeIngredient.recipe_id)).where(
            RecipeIngredient.ingredient_id == ingredient_id)
        usage_count = await self.ingredient_repo.db.scalar(count_stmt)
        if usage_count > 0:
            raise BusinessRuleException(f"无法删除，该食材正在被 {usage_count} 个菜谱使用")

        try:
            await self.ingredient_repo.delete(ingredient_to_delete)
            await self.ingredient_repo.commit()
        except Exception as e:
            self.logger.error(f"删除食材 {ingredient_id} 失败: {e}")
            await self.ingredient_repo.rollback()
            raise e