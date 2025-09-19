# app/services/recipe_service.py
import asyncio
import os
from typing import Dict, Any, List, Union, Optional, TYPE_CHECKING, Set
from uuid import UUID

from fastapi import Depends
from sqlalchemy import delete
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import select

from app.core.exceptions import NotFoundException, ConcurrencyConflictException
from app.core.exceptions.base_exception import PermissionDeniedException
from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.common.category_model import RecipeCategoryLink
from app.models.files.file_record import FileRecord
from app.models.recipes.recipe import Recipe, RecipeIngredient, RecipeTagLink, RecipeStep, RecipeStepImageLink, \
    RecipeGalleryLink
from app.repo.crud.common.category_repo import CategoryRepository
from app.repo.crud.file.file_record_repo import FileRecordRepository
from app.schemas.file.file_schemas import AvatarLinkDTO, RecipeImageLinkDTO
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
from app.schemas.file.file_record_schemas import FileRecordUpdate

if TYPE_CHECKING :
    from app.services.file.file_service import FileService
    from app.services.file.file_record_service import FileRecordService

class RecipeService(BaseService):
    def __init__(
            self,
            factory: RepositoryFactory,
            current_user: Optional[UserContext] = None,
    ):
        super().__init__()
        self.factory = factory
        self.current_user = current_user
        # 从工厂获取所有需要的 Repository 实例
        self.recipe_repo: RecipeRepository = factory.get_repo_by_type(RecipeRepository)
        self.tag_repo: TagRepository = factory.get_repo_by_type(TagRepository)
        self.ingredient_repo: IngredientRepository = factory.get_repo_by_type(IngredientRepository)
        self.file_repo: FileRecordRepository = factory.get_repo_by_type(FileRecordRepository)
        self.category_repo: CategoryRepository = factory.get_repo_by_type(CategoryRepository)
        # file_service = file_service
        # file_record_service = file_record_service


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

    async def get_recipe_details(self, recipe_id: UUID, current_user: Optional[UserContext] = None, view_mode: str = ViewMode.ACTIVE.value) -> Recipe:
        recipe = await self.recipe_repo.get_by_id_with_details(recipe_id, view_mode)
        if not recipe:
            raise NotFoundException("菜谱不存在")
        if current_user:
            recipe_policy.can_view(current_user, recipe, "菜谱")
        return recipe

    async def page_list_recipes(
            self, page: int,
            per_page: int,
            sort_by: List[str],
            filters: Dict[str, Any],
            current_user: Optional[UserContext] = None,
            view_mode: str = ViewMode.ACTIVE
    ) -> PageResponse[RecipeSummaryRead]:
        if current_user:
            recipe_policy.can_list(current_user, Recipe)

        # ▼▼▼ 【核心修改】将 pop 操作分解，以帮助静态分析器理解 ▼▼▼

        # 1. 先用 .get() 安全地获取值，这不会修改字典
        category_ids_to_expand = filters.get("category_ids__in")

        # 2. 从字典中移除这个键，确保它不会被传递给下一层
        if "category_ids__in" in filters:
            del filters["category_ids__in"]

        # 后续逻辑与之前完全相同
        if category_ids_to_expand:
            tasks = [
                self.category_repo.get_self_and_descendants_cte(cat_id)
                for cat_id in category_ids_to_expand
            ]

            results_list = await asyncio.gather(*tasks)

            all_target_category_ids: Set[UUID] = set()
            for category_list in results_list:
                for category in category_list:
                    all_target_category_ids.add(category.id)

            if all_target_category_ids:
                # 将处理好的最终结果 "放回" filters 字典
                filters["category_ids__in"] = list(all_target_category_ids)
            else:
                return PageResponse(items=[], total=0, page=page, per_page=per_page, total_pages=0)

        return await self.recipe_repo.get_paged_recipes(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            filters=filters,
            view_mode=view_mode
        )

    async def create_recipe(
            self,
            recipe_in: RecipeCreate,
            user_context: UserContext,
            file_service: "FileService",
            file_record_service: "FileRecordService"
    ) -> Recipe:
        """【V3】创建一个结构化的、支持富媒体的完整菜谱。"""
        recipe_policy.can_create(user_context, Recipe)
        # 提取用于创建 Recipe 主表的数据
        recipe_data = recipe_in.model_dump(exclude={
            "tags", "ingredients", "steps",
            "cover_image_id", "gallery_image_ids", "category_ids"
        })

        # 为外部操作的结果预先定义变量
        files_to_move: List[Dict[str, Any]] = []
        recipe_orm: Optional[Recipe] = None

        async with self.recipe_repo.db.begin_nested():
            # --- 阶段一: 数据库事务 ---
            recipe_orm = await self.recipe_repo.create(recipe_data)
            await self.recipe_repo.flush()  # 获取 recipe_orm.id
            # ▼▼▼ 【核心修复】▼▼▼
            # 2. 重新获取这个刚刚创建的对象，但这次要用我们强大的、
            #    带有预加载功能的方法，确保所有关系都被正确初始化！
            recipe_orm_with_relations = await self.recipe_repo.get_by_id_with_details(recipe_orm.id)
            if not recipe_orm_with_relations:
                # 这是一个不太可能发生的边缘情况，但做好防御性编程
                raise Exception("Failed to reload newly created recipe.")
            # 【核心修改】调用统一的关联处理方法
            await self._handle_recipe_relations(recipe_orm_with_relations, recipe_in)
            # ▼▼▼ 【4. 新增】收集所有需要移动的文件信息 ▼▼▼
            all_file_ids = []
            if recipe_in.cover_image_id:
                all_file_ids.append(recipe_in.cover_image_id)
            if recipe_in.gallery_image_ids:
                all_file_ids.extend(recipe_in.gallery_image_ids)
            for step in recipe_in.steps or []:
                if step.image_ids:
                    all_file_ids.extend(step.image_ids)
            if all_file_ids:
                unique_file_ids = list(set(all_file_ids))
                file_records = await self.file_repo.get_by_ids(unique_file_ids)
                if len(file_records) != len(unique_file_ids):
                    raise NotFoundException("一个或多个指定的图片文件不存在")
                for record in file_records:
                    if getattr(record, 'is_associated', False):
                        raise NotFoundException(f"文件 {record.original_filename} 已被使用，无法关联。")
                    temp_path = record.object_name
                    filename = os.path.basename(temp_path)
                    # 根据文件用途构建不同的最终路径
                    # (这是一个简化的例子，您可以设计更复杂的规则)
                    # if record.id == recipe_in.cover_image_id:
                    #     subfolder = "cover"
                    # else:
                    #     subfolder = "gallery"  # 简化处理，步骤图也放入gallery
                    permanent_path = f"recipes/{recipe_orm_with_relations.id}/{filename}"
                    files_to_move.append({"source": temp_path, "dest": permanent_path, "record_id": record.id})
                    # 更新数据库记录
                    await file_record_service.update_file_record(
                        record.id, FileRecordUpdate(object_name=permanent_path, is_associated=True),
                    )
            # ▲▲▲ 新增结束 ▲▲▲
            # --- 阶段二: 外部非事务性操作 ---
        if files_to_move:
            for move_op in files_to_move:
                try:
                    await file_service.move_physical_file(
                        source_key=move_op["source"],
                        destination_key=move_op["dest"],
                        profile_name="recipe_images"
                    )
                except Exception as move_error:
                    self.logger.critical(
                        f"CRITICAL: Recipe {recipe_orm_with_relations.id} DB created, but failed to move image from {move_op['source']} to {move_op['dest']}. Error: {move_error}")
            # 刷新后返回完整的菜谱对象
        return await self.get_recipe_details(recipe_orm_with_relations.id, user_context)


    async def update_recipe(
            self,
            recipe_id: UUID,
            recipe_in: RecipeUpdate,
            user_context: UserContext,
            file_service: "FileService"  # 1. 在这里添加 file_service 参数
    ) -> Recipe:
        """【最终版】更新菜谱，采用“购物车”模式，一次性处理所有变更。"""
        recipe_orm = await self.get_recipe_details(recipe_id, user_context)
        recipe_policy.can_update(user_context, recipe_orm)

        # 提取用于更新 Recipe 主表的常规字段
        update_data = recipe_in.model_dump(
            exclude_unset=True,
            exclude={"tags", "ingredients", "steps", "cover_image_id", "gallery_image_ids", "category_ids",
                     "images_to_add", "images_to_delete", "images_order"}  # 排除图片操作字段
        )
        async with self.recipe_repo.db.begin_nested():
            # --- 开启一个大事务 ---
            if update_data:
                await self.recipe_repo.update(recipe_orm, update_data)

            # 调用统一的关联处理方法处理 tags, ingredients, steps, categories 等
            await self._handle_recipe_relations(recipe_orm, recipe_in)

            # 【核心逻辑】处理图片集合的“差量”更新
            if recipe_in.images_to_delete:
                await self.remove_images_from_gallery(
                    recipe_id,
                    recipe_in.images_to_delete,
                    user_context,
                    file_service
                )

            if recipe_in.images_to_add:
                await self.add_images_to_gallery(recipe_id, recipe_in.images_to_add, user_context)

        # 刷新并返回最新数据
        return await self.get_recipe_details(recipe_id, user_context)

    # =================================================================
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心新增图片管理方法 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # =================================================================

    async def _cleanup_old_file_records(self, record_id: Optional[UUID]):
        if not record_id:
            return
        old_record_repo = self.factory.get_repo_by_type(FileRecordRepository)
        old_record = await old_record_repo.get_by_id(record_id)
        if old_record:
            await old_record_repo.soft_delete(old_record)

    async def _cleanup_old_file(
            self,
            record_id: Optional[UUID],
            profile_name: str,
            file_service: "FileService"  # <-- 新增参数
    ):
        """【新增】一个可复用的、用于清理旧文件（物理文件+DB记录）的辅助方法。"""
        if not record_id:
            return

        # 1. 在事务内软删除DB记录
        old_record = await self.file_repo.get_by_id(record_id)
        if old_record:
            old_object_name = old_record.object_name
            await self.file_repo.soft_delete(old_record)  # 此操作不 commit

            # 2. 在事务成功后，再去删除物理文件
            try:
                await file_service.delete_file(old_object_name, profile_name=profile_name)
            except Exception as e:
                self.logger.error(
                    f"DB record for {old_object_name} deleted, but failed to delete physical file. Error: {e}")

    async def link_new_cover_image(
            self,
            recipe_id: UUID,
            file_dto: RecipeImageLinkDTO,
            user_context: UserContext,
            file_service: "FileService",  # <-- 新增参数
            file_record_service: "FileRecordService"  # <-- 新增参数
    ) -> Recipe:
        """【最终版】原子化地替换菜谱封面图（一对一替换）。"""
        recipe_orm = await self.get_recipe_details(recipe_id, user_context)

        old_cover_record_id = recipe_orm.cover_image_id
        old_cover_object_name = recipe_orm.cover_image.object_name if recipe_orm.cover_image else None

        async with self.recipe_repo.db.begin_nested():
            # --- 数据库事务开始 ---
            # 1. 登记新文件
            new_file_record = await file_record_service.register_uploaded_file(
                object_name=file_dto.object_name,
                original_filename=file_dto.original_filename,
                content_type=file_dto.content_type,
                file_size=file_dto.file_size,
                profile_name="recipe_images",
                uploader_context=user_context,
                etag=file_dto.etag,
            )

            # 2. 更新菜谱记录，关联新的封面图ID
            recipe_orm.cover_image_id = new_file_record.id
            self.recipe_repo.db.add(recipe_orm)

            # 【优化】清理旧的DB记录也在事务内完成
            if old_cover_record_id:
                await self._cleanup_old_file_records(old_cover_record_id)

        # --- 事务成功后，清理外部【物理文件】 ---
        if old_cover_record_id:
            old_record = await self.file_repo.get_by_id_including_deleted(old_cover_record_id)
            if old_record and old_record.object_name:
                try:
                    await file_service.delete_file(old_record.object_name, profile_name="recipe_images")
                except Exception as e:
                    self.logger.error(f"DB updated, 但删除旧封面图物理文件 {old_record.object_name} 失败: {e}")

        return await self.get_recipe_details(recipe_id)

    async def add_images_to_gallery(self, recipe_id: UUID, file_record_ids: List[UUID], user_context: UserContext,
                                    ) -> None:
        """【新增】为一个已存在的菜谱图库批量新增图片。"""
        recipe = await self.get_recipe_details(recipe_id, user_context)
        file_records = await self.file_repo.get_by_ids(file_record_ids)
        if len(file_records) != len(set(file_record_ids)):
            raise NotFoundException("一个或多个要关联的文件记录不存在")

        async with self.recipe_repo.db.begin_nested():
            await self.recipe_repo.add_gallery_images(recipe, file_record_ids)


    async def remove_images_from_gallery(
            self,
            recipe_id: UUID,
            image_record_ids: List[UUID],
            user_context: UserContext,
            file_service: "FileService",  # <-- 新增参数
    ) -> None:
        """【新增】从菜谱图库中批量删除图片。"""
        recipe = await self.get_recipe_details(recipe_id, user_context)
        # 验证这些图片确实属于这个菜谱... (此处省略，实际项目中应添加)

        records_to_delete = await self.file_repo.get_by_ids(image_record_ids)
        if len(records_to_delete) != len(set(image_record_ids)):
            raise NotFoundException("一个或多个要删除的图片记录不存在")

        object_names_to_delete = [r.object_name for r in records_to_delete]

        async with self.recipe_repo.db.begin_nested():
            # DB 事务
            await self.recipe_repo.remove_gallery_images(recipe, image_record_ids)
            await self.file_repo.soft_delete_by_ids(image_record_ids)


        # 外部文件清理
        if object_names_to_delete:
            try:
                await file_service.delete_files(object_names_to_delete, profile_name="recipe_images")
            except Exception as e:
                self.logger.error(
                    f"DB records deleted, but failed to delete physical files: {object_names_to_delete}. Error: {e}")

    async def delete_recipe(self, recipe_id: UUID, user_context: UserContext) -> None:
        """【修改后】软删除指定菜谱。"""
        async with self.recipe_repo.db.begin_nested():
            recipe_to_delete = await self.recipe_repo.get_by_id(recipe_id)
            if not recipe_to_delete:
                raise NotFoundException("菜谱不存在")
            recipe_policy.can_delete(user_context, recipe_to_delete)
            await self.recipe_repo.soft_delete(recipe_to_delete)

    # =================================================================
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心新增功能 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # =================================================================
    # async def batch_delete_recipes(self, recipe_ids: List[UUID], current_user: UserContext) -> int:
    #     if not recipe_ids:
    #         return 0
    #
    #     recipes_to_delete = await self.recipe_repo.get_by_ids(recipe_ids)
    #     if len(recipes_to_delete) != len(set(recipe_ids)):
    #         raise NotFoundException("一个或多个指定的菜谱不存在")
    #
    #     # 【权限检查】在循环中复用权限检查
    #     for recipe in recipes_to_delete:
    #         recipe_policy.can_delete(current_user, recipe)
    #
    #     try:
    #         deleted_count = await self.recipe_repo.soft_delete_by_ids(recipe_ids)
    #         await self.recipe_repo.commit()
    #         return deleted_count
    #     except Exception as e:
    #         self.logger.error(f"批量删除菜谱失败: {e}")
    #         await self.recipe_repo.rollback()
    #         raise e

    async def remove_images_from_step(
            self,
            recipe_id: UUID,
            step_id: UUID,
            image_record_ids: List[UUID],
            user_context: UserContext,
            file_service: "FileService",
    ) -> None:
        """【新增】从菜谱步骤中批量删除图片(包含物理文件)。"""

        # 1. 权限与存在性检查
        recipe = await self.get_recipe_details(recipe_id, user_context)
        step_exists = any(step.id == step_id for step in recipe.steps)
        if not step_exists:
            raise NotFoundException(f"Step with id {step_id} not found in recipe {recipe_id}")

        # 2. 验证要删除的图片记录确实存在
        records_to_delete = await self.file_repo.get_by_ids(image_record_ids)
        if len(records_to_delete) != len(set(image_record_ids)):
            raise NotFoundException("一个或多个要删除的图片记录不存在")

        # 3. 记下物理文件的 object_name，以便在事务成功后删除
        object_names_to_delete = [r.object_name for r in records_to_delete]

        async with self.recipe_repo.db.begin_nested():
            await self.recipe_repo.remove_step_images(step_id, image_record_ids)
            await self.file_repo.soft_delete_by_ids(image_record_ids)

        # 【修改】文件清理逻辑现在是可达的
        if object_names_to_delete:
            try:
                await file_service.delete_files(object_names_to_delete, profile_name="recipe_images")
            except Exception as e:
                self.logger.error(
                    f"DB records deleted for step {step_id}, but failed to delete physical files: {object_names_to_delete}. Error: {e}")

    async def add_images_to_step(
            self,
            recipe_id: UUID,
            step_id: UUID,
            file_record_ids: List[UUID],
            user_context: UserContext,
    ) -> None:
        """【新增】为一个已存在的菜谱步骤批量新增图片。"""

        # 1. 权限与存在性检查
        recipe = await self.get_recipe_details(recipe_id, user_context)

        # 2. 【核心校验】确认该步骤确实属于该菜谱
        step_exists = any(step.id == step_id for step in recipe.steps)
        if not step_exists:
            raise NotFoundException(f"Step with id {step_id} not found in recipe {recipe_id}")

        # 3. 校验要关联的文件记录是否存在
        file_records = await self.file_repo.get_by_ids(file_record_ids)
        if len(file_records) != len(set(file_record_ids)):
            raise NotFoundException("一个或多个要关联的文件记录不存在")

        async with self.recipe_repo.db.begin_nested():
            await self.recipe_repo.add_step_images(step_id, file_record_ids)

    async def batch_delete_recipes(self, recipe_ids: List[UUID], current_user: UserContext) -> int:
        """【修改后】批量软删除菜谱。"""
        if not recipe_ids:
            return 0

        async with self.recipe_repo.db.begin_nested():
            recipes_to_delete = await self.recipe_repo.get_by_ids(recipe_ids)
            if len(recipes_to_delete) != len(set(recipe_ids)):
                raise NotFoundException("一个或多个指定的菜谱不存在")

            for recipe in recipes_to_delete:
                recipe_policy.can_delete(current_user, recipe)

            return await self.recipe_repo.soft_delete_by_ids(recipe_ids)

    async def restore_recipes(self, recipe_ids: List[UUID], current_user: UserContext) -> int:
        """批量恢复软删除的菜谱。"""
        if not recipe_ids:
            return 0

        async with self.recipe_repo.db.begin_nested():
            recipes_to_restore = await self.recipe_repo.get_by_ids(recipe_ids, view_mode=ViewMode.DELETED.value)
            if len(recipes_to_restore) != len(set(recipe_ids)):
                raise NotFoundException("一个或多个要恢复的菜谱不存在于回收站中。")

            # 权限检查：确保用户有权操作这些菜谱（即使在回收站中）
            for recipe in recipes_to_restore:
                recipe_policy.can_update(current_user, recipe)  # 恢复可视为一种更新操作

            return await self.recipe_repo.restore_by_ids(recipe_ids)

    async def hard_delete_recipes(
            self,
            recipe_ids: List[UUID],
            current_user: UserContext,
            file_service: "FileService"
    ) -> int:
        """批量永久删除菜谱，并清理所有关联的物理文件。"""
        if not recipe_ids:
            return 0

        files_to_delete_after_commit: List[FileRecord] = []
        deleted_count = 0

        async with self.recipe_repo.db.begin_nested():
            recipes_to_delete = await self.recipe_repo.get_by_ids(recipe_ids, view_mode=ViewMode.DELETED.value)
            if len(recipes_to_delete) != len(set(recipe_ids)):
                raise NotFoundException("一个或多个要永久删除的菜谱不存在于回收站中。")

            for recipe in recipes_to_delete:
                recipe_policy.can_delete(current_user, recipe)  # 权限检查

            # 1. 在事务内，收集所有需要删除的文件记录
            files_to_delete_after_commit = await self.recipe_repo.get_all_associated_file_records(recipe_ids)

            # 1. 找到所有待刪除菜譜下的所有步驟 ID
            steps_to_delete_stmt = select(RecipeStep.id).where(RecipeStep.recipe_id.in_(recipe_ids))
            steps_result = await self.recipe_repo.db.execute(steps_to_delete_stmt)
            step_ids = steps_result.scalars().all()

            # 2. 如果找到了步驟，就先清理最深層的依賴：步驟-圖片關聯
            if step_ids:
                await self.recipe_repo.db.execute(
                    delete(RecipeStepImageLink).where(RecipeStepImageLink.step_id.in_(step_ids))
                )

            # 2. 软删除文件记录（以便保留审计信息）
            if file_ids_to_soft_delete := [f.id for f in files_to_delete_after_commit]:
                await self.file_repo.soft_delete_by_ids(file_ids_to_soft_delete)

            # 清理 recipe_tag_link (已有的)
            await self.recipe_repo.db.execute(
                delete(RecipeTagLink).where(RecipeTagLink.recipe_id.in_(recipe_ids))
            )

            # 2. 清理多对多关联：分类 (recipe_category_link)
            await self.recipe_repo.db.execute(
                delete(RecipeCategoryLink).where(RecipeCategoryLink.recipe_id.in_(recipe_ids))
            )

            await self.recipe_repo.db.execute(
                delete(RecipeGalleryLink).where(RecipeGalleryLink.recipe_id.in_(recipe_ids)))  # <-- 【核心新增】

            # 【核心新增】清理 recipe_ingredient
            await self.recipe_repo.db.execute(
                delete(RecipeIngredient).where(RecipeIngredient.recipe_id.in_(recipe_ids))
            )

            # 4. 【核心新增】清理一对多关联：步骤 (recipe_step)
            await self.recipe_repo.db.execute(
                delete(RecipeStep).where(RecipeStep.recipe_id.in_(recipe_ids))
            )

            # 3. 物理删除菜谱记录 (这会自动清理 recipe_tag_link 等关联表)
            deleted_count = await self.recipe_repo.hard_delete_by_ids(recipe_ids)

        # --- 事务成功后，开始清理外部物理文件 ---
        if files_to_delete_after_commit:
            object_names_to_delete = [f.object_name for f in files_to_delete_after_commit if f.object_name]
            if object_names_to_delete:
                try:
                    await file_service.delete_files(object_names_to_delete, profile_name="recipe_images")
                except Exception as e:
                    self.logger.error(
                        f"DB records for recipes {recipe_ids} deleted, but failed to delete physical files: {object_names_to_delete}. Error: {e}")

        return deleted_count

    async def remove_recipe_cover_image(
            self,
            recipe_id: UUID,
            user_context: UserContext
    ) -> None:
        """
        解除并彻底删除一个菜谱的封面图片。
        这个方法是“解除关联”这个问题的标准解决方案。
        """
        # 1. 获取菜谱并检查权限
        recipe = await self.recipe_repo.get_by_id(recipe_id)
        if not recipe:
            raise NotFoundException("菜谱不存在")

        recipe_policy.can_update(user_context, recipe)  # 删除封面图属于更新操作

        if not recipe.cover_image_id:
            self.logger.info(f"菜谱 {recipe_id} 没有封面图片，无需操作。")
            return

        file_to_delete_id = recipe.cover_image_id

        # 2. 在一个事务中，将 recipe 表中的外键设为 NULL
        async with self.recipe_repo.db.begin_nested():
            recipe.cover_image_id = None
            self.recipe_repo.db.add(recipe)

        # 3. 解除关联成功后，调用文件服务进行彻底删除
        # 我们需要先获取 FileRecord 对象
        record_to_delete = await self.file_record_service.file_repo.get_by_id_including_deleted(file_to_delete_id)
        if record_to_delete:
            await self.file_record_service.delete_file_and_record(
                record=record_to_delete,
                hard_delete_db=True
            )
        else:
            self.logger.warning(f"尝试删除文件记录 {file_to_delete_id}，但未找到该记录。")