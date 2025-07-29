# app/services/tag_service.py

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select, func

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipes.recipe import Tag, RecipeTagLink  # 导入 RecipeTagLink 用于检查
from app.schemas.recipes.tag_schemas import TagCreate, TagUpdate, TagRead
from app.repo.crud.recipes.tag_repo import TagRepository
from app.repo.crud.common.base_repo import PageResponse
from app.services._base_service import BaseService


class TagService(BaseService):
    def __init__(self, factory: RepositoryFactory):
        super().__init__()
        self.factory = factory
        self.tag_repo: TagRepository = factory.get_repo_by_type(TagRepository)

    async def get_tag_by_id(self, tag_id: UUID) -> Tag:
        """获取单个标签，未找到则抛出业务异常。"""
        tag = await self.tag_repo.get_by_id(tag_id)
        if not tag:
            raise NotFoundException("标签不存在")
        return tag

    async def page_list_tags(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any]
    ) -> PageResponse[TagRead]:
        """获取标签分页列表，并转换为 DTO。"""
        paged_tags_orm = await self.tag_repo.get_paged_tags(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}
        )
        # 将 ORM 对象列表转换为 Pydantic DTO 列表
        paged_tags_orm.items = [TagRead.model_validate(item) for item in paged_tags_orm.items]
        return paged_tags_orm

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
            await self.tag_repo.delete(tag_to_delete)
            await self.tag_repo.commit()
        except Exception as e:
            self.logger.error(f"删除标签 {tag_id} 失败: {e}")
            await self.tag_repo.rollback()
            raise e