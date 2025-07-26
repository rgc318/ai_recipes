# app/repo/crud/tag_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipe import Tag
from app.schemas.recipes.tag_schemas import TagCreate, TagUpdate


class TagRepository(BaseRepository[Tag, TagCreate, TagUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        super().__init__(db=db, model=Tag, context=context)

    async def find_by_name(self, name: str) -> Optional[Tag]:
        """
        根据名称查找标签（大小写不敏感）。
        用于在创建/更新时检查名称是否重复。
        """
        # 使用 ilike 实现大小写不敏感的精确匹配
        stmt = self._base_stmt().where(self.model.name.ilike(name))
        return await self._run_and_scalar(stmt, "find_by_name")

    async def are_ids_valid(self, ids: List[UUID]) -> bool:
        """
        高效地检查一组ID是否都存在于 tag 表中。
        这是被 RecipeService 依赖的关键方法。
        """
        if not ids:
            return True  # 空列表视为有效

        # 使用 set 去重以提高效率
        unique_ids = set(ids)

        # 构建一个高效的 COUNT 查询
        stmt = select(func.count(self.model.id)).where(self.model.id.in_(unique_ids))

        result = await self.db.execute(stmt)
        existing_count = result.scalar_one()

        # 如果数据库中存在的数量与去重后的ID数量相同，则所有ID都有效
        return existing_count == len(unique_ids)

    async def get_paged_tags(
            self, *, page: int, per_page: int, filters: Dict[str, Any], sort_by: List[str]
    ) -> PageResponse[Tag]:
        """
        获取标签的分页列表。
        对于标签来说，没有复杂的 JOIN，所以直接调用父类方法即可。
        """
        return await self.get_paged_list(
            page=page, per_page=per_page, filters=filters, sort_by=sort_by
        )