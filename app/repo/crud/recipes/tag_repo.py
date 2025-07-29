# app/repo/crud/recipes/tag_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import Tag
from app.schemas.recipes.tag_schemas import TagCreate, TagUpdate


class TagRepository(BaseRepository[Tag, TagCreate, TagUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        super().__init__(db=db, model=Tag, context=context)

    # =================================================================
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心修正点 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # 将 find_or_create 方法移出 __init__，使其成为一个正确的类方法
    # =================================================================
    async def find_or_create(self, name: str) -> Tag:
        """
        查找或创建一个标签。
        这是一个原子化的操作，用于确保标签的唯一性，特别是在处理并发请求时。
        RecipeService 将严重依赖此方法来处理用户输入的自定义标签。

        Args:
            name: 标签的名称。

        Returns:
            一个已存在的或新创建的 Tag ORM 对象。
        """
        # 1. 对名称进行标准化处理，与前端保持一致
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Tag name cannot be empty.")

        # 2. 尝试根据名称查找已存在的标签 (大小写不敏感)
        #    我们使用 with_for_update() 来锁定可能匹配的行，
        #    这是防止并发创建重复标签的关键步骤 (处理竞态条件)。
        #    注意：这需要数据库支持行级锁，PostgreSQL 完美支持。
        try:
            stmt = select(self.model).where(self.model.name.ilike(normalized_name)).with_for_update()
            result = await self.db.execute(stmt)
            existing_tag = result.scalar_one()
            # 如果找到了，直接返回
            return existing_tag
        except NoResultFound:
            # 3. 如果没有找到，则创建一个新的
            self.logger.info(f"Tag '{normalized_name}' not found, creating a new one.")
            new_tag = self.model(name=normalized_name)
            self.db.add(new_tag)
            # 使用 flush 将新标签写入数据库会话，使其获得 ID 并可被后续操作引用
            await self.db.flush()
            # 刷新对象以获取数据库的最新状态
            await self.db.refresh(new_tag)
            return new_tag
        except Exception as e:
            # 任何其他异常都应被捕获和记录
            self.logger.error(f"Error in find_or_create for tag '{normalized_name}': {e}")
            raise

    # =================================================================

    async def find_by_name(self, name: str) -> Optional[Tag]:
        """
        根据名称查找标签（大小写不敏感）。
        用于在创建/更新时检查名称是否重复。
        """
        stmt = self._base_stmt().where(self.model.name.ilike(name))
        return await self._run_and_scalar(stmt, "find_by_name")

    async def are_ids_valid(self, ids: List[UUID]) -> bool:
        """
        高效地检查一组ID是否都存在于 tag 表中。
        这是被 RecipeService 依赖的关键方法。
        """
        if not ids:
            return True

        unique_ids = set(ids)
        stmt = select(func.count(self.model.id)).where(self.model.id.in_(unique_ids))
        result = await self.db.execute(stmt)
        existing_count = result.scalar_one()
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
