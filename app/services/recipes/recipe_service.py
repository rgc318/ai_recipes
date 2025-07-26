# app/services/recipe_service.py

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import NotFoundException, ConcurrencyConflictException
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipe import Recipe
from app.schemas.recipes.recipe_schemas import RecipeCreate, RecipeUpdate, RecipeRead  # 导入 RecipeRead
from app.repo.crud.recipes.recipe_repo import RecipeRepository
from app.repo.crud.recipes.tag_repo import TagRepository  # 假设已存在
from app.repo.crud.recipes.ingredient_repo import IngredientRepository  # 假设已存在
from app.repo.crud.common.base_repo import PageResponse
from app.services._base_service import BaseService


class RecipeService(BaseService):
    def __init__(self, factory: RepositoryFactory):
        super().__init__()
        self.factory = factory
        # 从工厂获取所有需要的 Repository 实例
        self.recipe_repo: RecipeRepository = factory.get_repo_by_type(RecipeRepository)
        self.tag_repo: TagRepository = factory.get_repo_by_type(TagRepository)
        self.ingredient_repo: IngredientRepository = factory.get_repo_by_type(IngredientRepository)

    async def get_recipe_details(self, recipe_id: UUID) -> Recipe:
        """
        获取单个菜谱的完整信息。如果未找到，则抛出业务异常。
        """
        recipe = await self.recipe_repo.get_by_id_with_details(recipe_id)
        if not recipe:
            raise NotFoundException("菜谱不存在")
        return recipe

    async def page_list_recipes(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any]
    ) -> PageResponse[RecipeRead]:
        """
        获取菜谱分页列表。
        此方法现在只是一个简单的代理，将参数直接传递给 Repository。
        """
        # 直接调用 Repository 中已经封装好的、强大的分页方法
        paged_recipes_orm = await self.recipe_repo.get_paged_recipes(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}
        )

        # 将 ORM 对象列表转换为 Pydantic DTO 列表
        paged_recipes_orm.items = [RecipeRead.model_validate(item) for item in paged_recipes_orm.items]

        return paged_recipes_orm

    async def create_recipe(self, recipe_in: RecipeCreate, user_context_id: UUID) -> Recipe:
        """
        【事务性】创建一个完整的菜谱，包含基本信息、标签和配料。
        """
        # 1. 从输入数据中分离出关联ID
        recipe_data = recipe_in.model_dump(exclude={"tag_ids", "ingredients"})
        tag_ids = recipe_in.tag_ids or []
        ingredients_data = recipe_in.ingredients or []

        # 2. 【业务校验】在事务开始前，校验所有关联ID的有效性
        if tag_ids:
            if not await self.tag_repo.are_ids_valid(tag_ids):
                raise NotFoundException("一个或多个指定的标签不存在")
        if ingredients_data:
            ingredient_ids = [ing.ingredient_id for ing in ingredients_data]
            if not await self.ingredient_repo.are_ids_valid(ingredient_ids):
                raise NotFoundException("一个或多个指定的食材不存在")

        try:
            # 3. 【核心操作】开始构建菜谱
            # a. 创建菜谱主对象
            recipe_data['created_by'] = user_context_id
            recipe_data['updated_by'] = user_context_id
            recipe_orm = await self.recipe_repo.create(recipe_data)
            await self.recipe_repo.flush()  # 立即刷入数据库以获取 recipe_orm.id

            # b. 设置标签和配料关联
            if tag_ids:
                await self.recipe_repo.set_recipe_tags(recipe_orm.id, tag_ids)
            if ingredients_data:
                await self.recipe_repo.set_recipe_ingredients(recipe_orm.id, ingredients_data)

            # 4. 【提交事务】所有操作成功，提交整个事务
            await self.recipe_repo.commit()

            # 5. 刷新对象以加载完整的关联数据
            await self.recipe_repo.refresh(recipe_orm)
            return recipe_orm

        except Exception as e:
            self.logger.error(f"创建菜谱失败: {e}")
            # 发生任何错误，回滚事务
            await self.recipe_repo.rollback()
            raise e

    async def update_recipe(self, recipe_id: UUID, recipe_in: RecipeUpdate, user_context_id: UUID) -> Recipe:
        """
        【事务性与并发安全】更新一个菜谱。
        """
        # 1. 获取要更新的菜谱，同时处理“未找到”的情况
        recipe_orm = await self.get_recipe_details(recipe_id)

        # 2. 分离更新数据
        update_data = recipe_in.model_dump(exclude_unset=True)
        tag_ids = update_data.pop("tag_ids", None)
        ingredients_data = update_data.pop("ingredients", None)

        # 注入更新人信息
        update_data['updated_by'] = user_context_id

        try:
            # 3. 【业务校验与执行】
            # a. 更新标签 (如果提供了)
            if tag_ids is not None:
                if not await self.tag_repo.are_ids_valid(tag_ids):
                    raise NotFoundException("一个或多个指定的标签不存在")
                await self.recipe_repo.set_recipe_tags(recipe_id, tag_ids)

            # b. 更新配料 (如果提供了)
            if ingredients_data is not None:
                ingredient_ids = [ing.ingredient_id for ing in ingredients_data]
                if not await self.ingredient_repo.are_ids_valid(ingredient_ids):
                    raise NotFoundException("一个或多个指定的食材不存在")
                await self.recipe_repo.set_recipe_ingredients(recipe_id, ingredients_data)

            # c. 更新菜谱主表字段
            if update_data:
                await self.recipe_repo.update(recipe_orm, update_data)

            # 4. 【提交事务】
            await self.recipe_repo.commit()
            await self.recipe_repo.refresh(recipe_orm)
            return recipe_orm

        except StaleDataError:
            # 捕获乐观锁冲突
            await self.recipe_repo.rollback()
            raise ConcurrencyConflictException("操作失败，菜谱数据已被他人修改，请刷新后重试")
        except Exception as e:
            self.logger.error(f"更新菜谱 {recipe_id} 失败: {e}")
            await self.recipe_repo.rollback()
            raise e

    async def delete_recipe(self, recipe_id: UUID, user_context_id: UUID) -> None:
        """
        【事务性】软删除一个菜谱。
        """
        # 获取菜谱，确保它存在，同时也方便后续操作
        recipe_to_delete = await self.get_recipe_details(recipe_id)

        # 在软删除前，也可以选择清理关联（可选，取决于业务需求）
        # await self.recipe_repo.set_recipe_tags(recipe_id, [])
        # await self.recipe_repo.set_recipe_ingredients(recipe_id, [])

        try:
            # 为软删除操作注入删除人信息
            self.recipe_repo.context['user_id'] = user_context_id
            await self.recipe_repo.soft_delete(recipe_to_delete)
            await self.recipe_repo.commit()
        except Exception as e:
            self.logger.error(f"删除菜谱 {recipe_id} 失败: {e}")
            await self.recipe_repo.rollback()
            raise e