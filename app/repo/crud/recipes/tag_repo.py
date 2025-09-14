# app/repo/crud/recipes/tag_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types.common import ModelType
from app.enums.query_enums import ViewMode
from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import Tag, RecipeTagLink
from app.schemas.recipes.tag_schemas import TagCreate, TagUpdate, TagRead
from sqlalchemy.dialects.postgresql import insert as pg_insert

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

    # async def get_paged_tags(
    #         self, *,
    #         page: int,
    #         per_page: int,
    #         filters: Dict[str, Any],
    #         sort_by: List[str],
    #         view_mode: str = ViewMode.ACTIVE.value  # <-- 【新增】接收 view_mode 参数
    # ) -> PageResponse[TagRead]:
    #     """
    #     获取标签的分页列表，并附带每个标签关联的菜谱数量。
    #     """
    #     recipe_count_col = func.count(RecipeTagLink.recipe_id).label("recipe_count")
    #
    #     # 1. 定义我们需要 GROUP BY 的所有列
    #     #    这包括 Tag 模型的所有核心字段
    #     group_by_columns = [getattr(self.model, col.name) for col in self.model.__table__.columns]
    #
    #     # 2. 构建基础查询，这次我们直接从主模型开始
    #     stmt = (
    #         select(self.model, recipe_count_col)
    #         .outerjoin(RecipeTagLink, self.model.id == RecipeTagLink.tag_id)
    #         .group_by(*group_by_columns)  # 【核心修复】按所有非聚合列进行分组
    #     )
    #
    #     if view_mode == ViewMode.ACTIVE:
    #         stmt = stmt.where(self.model.is_deleted == False)
    #     elif view_mode == ViewMode.DELETED:
    #         stmt = stmt.where(self.model.is_deleted == True)
    #
    #     filter_value = filters.get("name__ilike")
    #     if filter_value:  # 👈 增加一个判断，确保值不是 None 或空字符串
    #         stmt = stmt.where(self.model.name.ilike(f'%{filter_value}%'))
    #
    #
    #     # 4. 计算总数
    #     count_stmt = select(func.count()).select_from(stmt.subquery())
    #     total_records = await self._run_and_scalar(count_stmt, "count_paged_tags")
    #
    #     if total_records == 0:
    #         return self._create_page_response(items=[], total=0, page=page, per_page=per_page)
    #
    #     # 5. 应用排序
    #     order_clauses = []
    #     for sort_field in sort_by:
    #         field_name = sort_field.lstrip('-')
    #         direction = "desc" if sort_field.startswith('-') else "asc"
    #
    #         # 【关键】排序时，需要正确引用列
    #         order_by_col = None
    #         if field_name == 'recipe_count':
    #             order_by_col = recipe_count_col
    #         else:
    #             # 对于模型字段，需要从 GROUP BY 的列中获取，以确保一致
    #             for col in group_by_columns:
    #                 if col.name == field_name:
    #                     order_by_col = col
    #                     break
    #
    #         if order_by_col is not None:
    #             order_clauses.append(getattr(order_by_col, direction)())
    #
    #     if order_clauses:
    #         stmt = stmt.order_by(*order_clauses)
    #
    #     # 6. 应用分页
    #     offset = (page - 1) * per_page
    #     stmt = stmt.limit(per_page).offset(offset)
    #
    #     # 7. 执行查询并处理结果
    #     result = await self.db.execute(stmt)
    #     orm_items_with_count = result.all()  # result.all() 返回 (Tag, recipe_count) 元组
    #
    #     dto_items = []
    #     for item_orm, count in orm_items_with_count:
    #         # 使用 model_validate 从 ORM 对象创建 DTO
    #         item_dto = TagRead.model_validate(item_orm)
    #         # 然后安全地给 DTO 的 recipe_count 字段赋值
    #         item_dto.recipe_count = count
    #         dto_items.append(item_dto)
    #
    #     return self._create_page_response(
    #         items=dto_items,
    #         total=total_records,
    #         page=page,
    #         per_page=per_page
    #     )

    async def get_paged_tags(
            self, *,
            page: int,
            per_page: int,
            filters: Dict[str, Any],
            sort_by: List[str],
            view_mode: str = ViewMode.ACTIVE.value
    ) -> PageResponse[TagRead]:
        """
        【重构后】获取标签的分页列表，并附带每个标签关联的菜谱数量。
        """
        recipe_count_col = func.count(RecipeTagLink.recipe_id).label("recipe_count")

        # 1. 只需构建核心查询语句
        stmt = (
            select(self.model, recipe_count_col)
            .outerjoin(RecipeTagLink, self.model.id == RecipeTagLink.tag_id)
            .group_by(self.model.id)  # 按主键分组即可
        )

        # 2. 将所有分页、过滤、排序的复杂工作交给强大的基类！
        paged_response = await self.get_paged_list(
            page=page,
            per_page=per_page,
            filters=filters,
            sort_by=sort_by,
            view_mode=view_mode,
            stmt_in=stmt,
            sort_map={'recipe_count': recipe_count_col},
            return_scalars=False
        )

        # 3. 处理基类返回的元组列表
        dto_items = []
        for item_orm, count in paged_response.items:
            item_dto = TagRead.model_validate(item_orm)
            item_dto.recipe_count = count if count is not None else 0
            dto_items.append(item_dto)

        # 4. 替换 PageResponse 中的 items 并返回
        paged_response.items = dto_items
        return paged_response
    # =================================================================
    # ▼▼▼ 为“合并标签”功能提前准备的辅助方法 ▼▼▼
    # =================================================================

    async def get_recipe_ids_for_tags(self, tag_ids: List[UUID]) -> List[UUID]:
        """根据一组标签ID，获取所有关联的、不重复的菜谱ID。"""
        if not tag_ids:
            return []
        stmt = select(RecipeTagLink.recipe_id).where(RecipeTagLink.tag_id.in_(tag_ids)).distinct()
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_links_for_tags(self, tag_ids: List[UUID]) -> None:
        """根据一组标签ID，删除 recipe_tag_link 中间表中的所有相关记录。"""
        if not tag_ids:
            return
        stmt = delete(RecipeTagLink).where(RecipeTagLink.tag_id.in_(tag_ids))
        await self.db.execute(stmt)

