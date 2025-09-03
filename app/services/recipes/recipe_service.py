# app/services/recipe_service.py

from typing import Dict, Any, List, Union, Optional
from uuid import UUID

from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import NotFoundException, ConcurrencyConflictException
from app.core.exceptions.base_exception import PermissionDeniedException
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipes.recipe import Recipe, RecipeIngredient
from app.repo.crud.common.category_repo import CategoryRepository
from app.repo.crud.file.file_record_repo import FileRecordRepository
from app.schemas.recipes.recipe_schemas import RecipeCreate, RecipeUpdate, RecipeRead, \
    RecipeSummaryRead, RecipeIngredientInput  # 导入 RecipeRead
from app.repo.crud.recipes.recipe_repo import RecipeRepository
from app.repo.crud.recipes.tag_repo import TagRepository  # 假设已存在
from app.repo.crud.recipes.ingredient_repo import IngredientRepository  # 假设已存在
from app.repo.crud.common.base_repo import PageResponse
from app.schemas.users.user_context import UserContext
from app.services._base_service import BaseService
# 【核心】导入我们最终版的、模块化的 RecipePolicy 单例
from app.core.permissions.recipes.recipes_permission import recipe_policy


class RecipeService(BaseService):
    def __init__(self, factory: RepositoryFactory):
        super().__init__()
        self.factory = factory
        # 从工厂获取所有需要的 Repository 实例
        self.recipe_repo: RecipeRepository = factory.get_repo_by_type(RecipeRepository)
        self.tag_repo: TagRepository = factory.get_repo_by_type(TagRepository)
        self.ingredient_repo: IngredientRepository = factory.get_repo_by_type(IngredientRepository)
        self.file_repo: FileRecordRepository = factory.get_repo_by_type(FileRecordRepository)
        self.category_repo: CategoryRepository = factory.get_repo_by_type(CategoryRepository)


    async def _process_tags(self, tag_inputs: List[Union[UUID, str]]) -> List[UUID]:
        """
        【新增】一个内部辅助方法，用于处理混合类型的标签输入。
        它会将字符串标签转换为已存在的或新创建的标签ID。
        """
        if not tag_inputs:
            return []

        final_tag_ids = set()
        ids_from_strings_to_validate = []

        for item in tag_inputs:
            if isinstance(item, UUID):
                # 先收集所有传入的UUID，稍后一次性验证
                final_tag_ids.add(item)

            elif isinstance(item, str) and item.strip():
                cleaned_value = item.strip()
                # 尝试将字符串解析为 UUID
                try:
                    tag_id = UUID(cleaned_value)
                    ids_from_strings_to_validate.append(tag_id)
                except ValueError:
                    # 如果解析失败 (说明它不是UUID格式)，那么它就是一个普通的标签名
                    # 执行“查找或创建”逻辑
                    tag_orm = await self.tag_repo.find_or_create(cleaned_value)
                    final_tag_ids.add(tag_orm.id)


        # 一次性验证所有传入的UUID是否存在
        if ids_from_strings_to_validate:
            if not await self.tag_repo.are_ids_valid(ids_from_strings_to_validate):
                raise NotFoundException("一个或多个指定的标签ID不存在")
            final_tag_ids.update(ids_from_strings_to_validate)

        return list(final_tag_ids)

    async def _process_ingredients(self, ingredients_data: List[RecipeIngredientInput]) -> List[RecipeIngredientInput]:
        """
        【最终修正版】智能处理食材输入，支持即创即用，并能正确处理前端传回的已选定对象。
        """
        if not ingredients_data:
            return []

        processed_ingredients_dto = []

        for item_in in ingredients_data:
            ingredient_value = item_in.ingredient
            ingredient_id = None

            # 1. 如果是 UUID，直接使用
            if isinstance(ingredient_value, UUID):
                ingredient_id = ingredient_value
            # 2. 如果是字符串，查找或创建
            elif isinstance(ingredient_value, str) and ingredient_value.strip():
                cleaned_value = ingredient_value.strip()
                if not cleaned_value:
                    continue

                # 尝试将字符串解析为 UUID
                try:
                    # 如果这行代码成功执行，说明它是一个有效的 UUID 字符串
                    ingredient_id = UUID(cleaned_value)
                except ValueError:
                    # 如果解析失败 (说明它不是UUID格式)，那么它就是一个普通的配料名
                    # 执行“查找或创建”逻辑
                    ingredient_orm = await self.ingredient_repo.find_or_create(cleaned_value)
                    ingredient_id = ingredient_orm.id
            # 3. 【新增】如果是字典 (来自 antd Select 的已选项)，提取其 value
            elif isinstance(ingredient_value, dict) and ingredient_value.get('value'):
                try:
                    ingredient_id = UUID(ingredient_value['value'])
                except (ValueError, TypeError):
                    # 如果 value 不是合法的 UUID，则忽略
                    self.logger.warning(f"Invalid UUID format in ingredient object: {ingredient_value}")
                    continue

            if not ingredient_id:
                continue

            # 构建净化后的 DTO
            processed_ingredients_dto.append(
                RecipeIngredientInput(
                    ingredient=ingredient_id,
                    unit_id=item_in.unit_id,
                    group=item_in.group,
                    quantity=item_in.quantity,
                    note=item_in.note
                )
            )

        # 对所有收集到的 UUID 进行一次性有效性校验
        all_ingredient_ids = [ing.ingredient for ing in processed_ingredients_dto]
        if all_ingredient_ids and not await self.ingredient_repo.are_ids_valid(all_ingredient_ids):
            raise NotFoundException("一个或多个指定的食材ID不存在")

        return processed_ingredients_dto

    async def _handle_recipe_relations(
            self, recipe_orm: Recipe, recipe_in: Union[RecipeCreate, RecipeUpdate]
    ):
        """【最终统一版】统一处理所有菜谱关联关系的内部方法。"""

        # 1. 处理标签
        if recipe_in.tags is not None:
            final_tag_ids = await self._process_tags(recipe_in.tags)
            # 【修改】传入 recipe_orm 对象
            await self.recipe_repo.set_recipe_tags(recipe_orm, final_tag_ids)

        # 2. 处理配料
        if recipe_in.ingredients is not None:
            processed_ingredient_orms: List[RecipeIngredient] = await self._process_ingredients(recipe_in.ingredients)
            await self.recipe_repo.set_recipe_ingredients(recipe_orm, processed_ingredient_orms)

        # 3. 处理结构化步骤 (此项已是正确的ORM模式，无需修改)
        if recipe_in.steps is not None:
            all_image_ids = [img_id for step in recipe_in.steps if step.image_ids for img_id in step.image_ids]
            if all_image_ids and not await self.file_repo.are_ids_valid(list(set(all_image_ids))):
                raise NotFoundException("步骤中引用了一个或多个不存在的图片ID")
            await self.recipe_repo.set_recipe_steps(recipe_orm, recipe_in.steps)

        # 4. 处理封面图片 (此项操作的是主对象字段，无需修改)
        if hasattr(recipe_in, 'cover_image_id'):
            cover_id = recipe_in.cover_image_id
            if cover_id and not await self.file_repo.are_ids_valid([cover_id]):
                raise NotFoundException("指定的封面图片ID不存在")
            await self.recipe_repo.update_cover_image(recipe_orm, cover_id)

        # 5. 处理画廊图片
        if recipe_in.gallery_image_ids is not None:
            if recipe_in.gallery_image_ids and not await self.file_repo.are_ids_valid(recipe_in.gallery_image_ids):
                raise NotFoundException("画廊中引用了一个或多个不存在的图片ID")
            # 【修改】传入 recipe_orm 对象
            await self.recipe_repo.set_recipe_gallery(recipe_orm, recipe_in.gallery_image_ids)

        # 6. 处理分类
        if recipe_in.category_ids is not None:
            if recipe_in.category_ids and not await self.category_repo.are_ids_valid(recipe_in.category_ids):
                raise NotFoundException("一个或多个指定的分类ID不存在")
            # 【修改】传入 recipe_orm 对象
            await self.recipe_repo.set_recipe_categories(recipe_orm, recipe_in.category_ids)

    async def get_recipe_details(self, recipe_id: UUID, current_user: Optional[UserContext] = None) -> Recipe:
        recipe = await self.recipe_repo.get_by_id_with_details(recipe_id)
        if not recipe:
            raise NotFoundException("菜谱不存在")
        if current_user:
            recipe_policy.can_view(current_user, recipe, "菜谱")
        return recipe

    async def page_list_recipes(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any], current_user: Optional[UserContext] = None
    ) -> PageResponse[RecipeSummaryRead]:
        if current_user:
            recipe_policy.can_list(current_user, Recipe)
        paged_recipes_orm = await self.recipe_repo.get_paged_recipes(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}
        )
        paged_recipes_orm.items = [RecipeSummaryRead.model_validate(item) for item in paged_recipes_orm.items]
        return paged_recipes_orm

    async def create_recipe(self, recipe_in: RecipeCreate, user_context: UserContext) -> Recipe:
        """【V3】创建一个结构化的、支持富媒体的完整菜谱。"""
        recipe_policy.can_create(user_context)
        # 提取用于创建 Recipe 主表的数据
        recipe_data = recipe_in.model_dump(
            exclude={"tags", "ingredients", "steps", "cover_image_id", "gallery_image_ids", "category_ids"}
        )

        try:
            # 1. 创建菜谱主对象
            recipe_orm = await self.recipe_repo.create(recipe_data)
            await self.recipe_repo.flush()

            # 2. 【核心修改】调用统一的关联处理方法
            await self._handle_recipe_relations(recipe_orm, recipe_in)

            # 3. 提交整个事务
            await self.recipe_repo.commit()
            await self.recipe_repo.refresh(recipe_orm)
            # 刷新后返回完整的菜谱对象
            return await self.get_recipe_details(recipe_orm.id)
        except Exception as e:
            self.logger.error(f"创建菜谱失败: {e}")
            await self.recipe_repo.rollback()
            raise e

    async def update_recipe(self, recipe_id: UUID, recipe_in: RecipeUpdate, user_context: UserContext) -> Recipe:
        """【V3】更新一个结构化的、支持富媒体的完整菜谱。"""
        recipe_orm = await self.get_recipe_details(recipe_id)
        if not recipe_orm:
            raise NotFoundException("菜谱不存在")
        recipe_policy.can_update(user_context, recipe_orm)
        # 提取用于更新 Recipe 主表的常规字段
        update_data = recipe_in.model_dump(
            exclude_unset=True,
            exclude={"tags", "ingredients", "steps", "cover_image_id", "gallery_image_ids", "category_ids"}
        )


        try:
            # 1. 更新常规字段
            if update_data:
                await self.recipe_repo.update(recipe_orm, update_data)

            # 2. 【核心修改】调用统一的关联处理方法
            #    注意：recipe_in 包含了所有可能更新的关联字段
            await self._handle_recipe_relations(recipe_orm, recipe_in)

            # 3. 提交整个事务
            await self.recipe_repo.commit()
            await self.recipe_repo.refresh(recipe_orm)
            return await self.get_recipe_details(recipe_id)
        except StaleDataError:
            await self.recipe_repo.rollback()
            raise ConcurrencyConflictException("操作失败，菜谱数据已被他人修改，请刷新后重试")
        except Exception as e:
            self.logger.error(f"更新菜谱 {recipe_id} 失败: {e}")
            await self.recipe_repo.rollback()
            raise e

    async def delete_recipe(self, recipe_id: UUID, user_context: UserContext) -> None:
        recipe_to_delete = await self.recipe_repo.get_by_id(recipe_id)
        if not recipe_to_delete:
            raise NotFoundException("菜谱不存在")

        recipe_policy.can_delete(user_context, recipe_to_delete)
        try:
            self.recipe_repo.context['user_id'] = user_context.id
            await self.recipe_repo.soft_delete(recipe_to_delete)
            await self.recipe_repo.commit()
        except Exception as e:
            self.logger.error(f"删除菜谱 {recipe_id} 失败: {e}")
            await self.recipe_repo.rollback()
            raise e

    # =================================================================
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心新增功能 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # =================================================================
    async def batch_delete_recipes(self, recipe_ids: List[UUID], current_user: UserContext) -> int:
        if not recipe_ids:
            return 0

        recipes_to_delete = await self.recipe_repo.get_by_ids(recipe_ids)
        if len(recipes_to_delete) != len(set(recipe_ids)):
            raise NotFoundException("一个或多个指定的菜谱不存在")

        # 【权限检查】在循环中复用权限检查
        for recipe in recipes_to_delete:
            recipe_policy.can_delete(current_user, recipe)

        try:
            deleted_count = await self.recipe_repo.soft_delete_by_ids(recipe_ids)
            await self.recipe_repo.commit()
            return deleted_count
        except Exception as e:
            self.logger.error(f"批量删除菜谱失败: {e}")
            await self.recipe_repo.rollback()
            raise e