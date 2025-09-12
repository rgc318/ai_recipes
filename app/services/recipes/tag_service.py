# app/services/tag_service.py

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select, func

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException
from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipes.recipe import Tag, RecipeTagLink  # 导入 RecipeTagLink 用于检查
from app.repo.crud.recipes.recipe_repo import RecipeRepository
from app.schemas.recipes.tag_schemas import TagCreate, TagUpdate, TagRead, TagMergePayload
from app.repo.crud.recipes.tag_repo import TagRepository
from app.repo.crud.common.base_repo import PageResponse
from app.services._base_service import BaseService

from sqlalchemy.dialects.postgresql import insert as pg_insert


class TagService(BaseService):
    def __init__(self, factory: RepositoryFactory):
        super().__init__()
        self.factory = factory
        self.tag_repo: TagRepository = factory.get_repo_by_type(TagRepository)
        self.recipe_repo: RecipeRepository = factory.get_repo_by_type(RecipeRepository)

    async def get_tag_by_id(self, tag_id: UUID, view_mode: str = ViewMode.ACTIVE.value) -> Tag:
        """【修改】获取单个标签，支持 view_mode。"""
        tag = await self.tag_repo.get_by_id(tag_id, view_mode=view_mode)
        if not tag:
            raise NotFoundException("标签不存在")
        return tag

    async def page_list_tags(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any], view_mode: str
    ) -> PageResponse[TagRead]:
        """【修改】获取标签分页列表，并将 view_mode 传递下去。"""
        paged_tags_dto = await self.tag_repo.get_paged_tags(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}, view_mode=view_mode
        )
        return paged_tags_dto

    async def create_tag(self, tag_in: TagCreate) -> Tag:
        """【事务性】创建新标签，并进行重名校验。"""
        # 业务规则：标签名不能重复（大小写不敏感）
        existing_tag = await self.tag_repo.find_by_name(tag_in.name)
        if existing_tag:
            raise AlreadyExistsException("已存在同名标签")

        try:
            new_tag = await self.tag_repo.create(tag_in)
            await self.tag_repo.commit()
            return new_tag
        except Exception as e:
            self.logger.error(f"创建标签失败: {e}")
            await self.tag_repo.rollback()
            raise e

    async def update_tag(self, tag_id: UUID, tag_in: TagUpdate) -> Tag:
        """【事务性】更新标签，并进行重名校验。"""
        tag_to_update = await self.get_tag_by_id(tag_id)
        update_data = tag_in.model_dump(exclude_unset=True)

        if not update_data:
            return tag_to_update  # 如果没有提供任何更新数据，直接返回

        # 业务规则：如果名称被修改，需要检查新名称是否与其它标签冲突
        if "name" in update_data and update_data["name"].lower() != tag_to_update.name.lower():
            existing_tag = await self.tag_repo.find_by_name(update_data["name"])
            if existing_tag and existing_tag.id != tag_id:
                raise AlreadyExistsException("更新失败，已存在同名标签")

        try:
            updated_tag = await self.tag_repo.update(tag_to_update, update_data)
            await self.tag_repo.commit()
            return updated_tag
        except Exception as e:
            self.logger.error(f"更新标签 {tag_id} 失败: {e}")
            await self.tag_repo.rollback()
            raise e

    async def delete_tag(self, tag_id: UUID) -> None:
        """【事务性】删除标签，并进行使用情况检查。"""
        tag_to_delete = await self.get_tag_by_id(tag_id)

        # 业务规则：不允许删除正在被任何菜谱使用的标签
        count_stmt = select(func.count(RecipeTagLink.recipe_id)).where(RecipeTagLink.tag_id == tag_id)
        usage_count = await self.tag_repo.db.scalar(count_stmt)
        if usage_count > 0:
            raise BusinessRuleException(f"无法删除，该标签正在被 {usage_count} 个菜谱使用")

        try:
            # 调用的是父类的 delete，它只在 session 中删除，不 commit
            await self.tag_repo.soft_delete(tag_to_delete)
            await self.tag_repo.commit()
        except Exception as e:
            self.logger.error(f"删除标签 {tag_id} 失败: {e}")
            await self.tag_repo.rollback()
            raise e

    async def merge_tags(self, payload: TagMergePayload) -> dict:
        """【新增】将多个源标签合并到一个目标标签。"""
        source_ids = list(set(payload.source_tag_ids))
        target_id = payload.target_tag_id

        async with self.tag_repo.db.begin():
            if target_id in source_ids:
                raise BusinessRuleException("目标标签不能是被合并的源标签之一。")
            if not await self.tag_repo.are_ids_valid(source_ids + [target_id]):
                raise NotFoundException("一个或多个指定的标签ID不存在。")

            recipe_ids_to_remap = await self.tag_repo.get_recipe_ids_for_tags(source_ids)
            if recipe_ids_to_remap:
                await self.recipe_repo.add_tags_to_recipes(recipe_ids_to_remap, [target_id])

            # 删除旧的关联关系和旧的标签
            await self.tag_repo.delete_links_for_tags(source_ids)
            await self.tag_repo.soft_delete_by_ids(source_ids)

        return {"merged_count": len(source_ids)}

    async def batch_delete_tags(self, tag_ids: List[UUID]) -> int:
        """
        【事务性】批量删除标签，并进行使用情况检查。
        """
        if not tag_ids:
            return 0

        unique_tag_ids = list(set(tag_ids))

        # --- 在一个事务中完成所有检查和操作 ---
        async with self.tag_repo.db.begin():
            # 1. 业务规则校验：确认所有要删除的标签都存在
            tags_to_delete = await self.tag_repo.get_by_ids(unique_tag_ids)
            if len(tags_to_delete) != len(unique_tag_ids):
                raise NotFoundException("一个或多个要删除的标签不存在。")

            # 2. 业务规则校验：确认所有标签都未被任何菜谱使用
            #    我们可以通过一次高效的查询来完成
            count_stmt = (
                select(func.count(RecipeTagLink.recipe_id))
                .where(RecipeTagLink.tag_id.in_(unique_tag_ids))
            )
            usage_count = await self.tag_repo.db.scalar(count_stmt)
            if usage_count > 0:
                # 为了更友好的提示，可以再查一下具体是哪些标签被使用了
                # 但一个总的错误提示通常也足够了
                raise BusinessRuleException(f"操作失败：选中的标签中仍有标签正在被菜谱使用，无法删除。")

            # 3. 执行批量软删除
            deleted_count = await self.tag_repo.soft_delete_by_ids(unique_tag_ids)

        return deleted_count

    async def restore_tags(self, tag_ids: List[UUID]) -> int:
        """【新增】批量恢复被软删除的标签。"""
        if not tag_ids:
            return 0

        async with self.tag_repo.db.begin():
            # 校验这些 ID 是否确实是已删除状态
            tags_to_restore = await self.tag_repo.get_by_ids(tag_ids, view_mode=ViewMode.DELETED.value)
            if len(tags_to_restore) != len(set(tag_ids)):
                raise NotFoundException("一个或多个要恢复的标签不存在于回收站中。")

            restored_count = await self.tag_repo.restore_by_ids(tag_ids)

        return restored_count

    async def hard_delete_tags(self, tag_ids: List[UUID]) -> int:
        """【新增】批量永久删除标签（高危操作）。"""
        if not tag_ids:
            return 0

        async with self.tag_repo.db.begin():
            # 业务规则：通常只允许永久删除那些已经被软删除的标签
            tags_to_delete = await self.tag_repo.get_by_ids(tag_ids, view_mode=ViewMode.DELETED.value)
            if len(tags_to_delete) != len(set(tag_ids)):
                raise NotFoundException("一个或多个要永久删除的标签不存在于回收站中。")

            # 1. 先删除所有与这些标签相关的菜谱关联
            await self.tag_repo.delete_links_for_tags(tag_ids)

            # 2. 再物理删除标签本身
            deleted_count = await self.tag_repo.hard_delete_by_ids(tag_ids)

        return deleted_count
