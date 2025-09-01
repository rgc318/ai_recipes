# app/repo/crud/recipes/category_repo.py

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.common.category_model import Category
from app.schemas.common.category_schemas import CategoryCreate, CategoryUpdate


class CategoryRepository(BaseRepository[Category, CategoryCreate, CategoryUpdate]):
    """
    CategoryRepository 提供了所有与分类相关的数据库操作。
    它特别包含了处理层级（树形）数据的方法。
    """

    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        super().__init__(db=db, model=Category, context=context)

    async def find_by_slug(self, slug: str) -> Optional[Category]:
        """根据 slug 查找分类，用于前端路由或唯一性校验。"""
        return await self.find_by_field(value=slug, field_name="slug")

    async def find_by_name(self, name: str) -> Optional[Category]:
        """根据名称查找分类（大小写不敏感），用于防止重名。"""
        stmt = self._base_stmt().where(self.model.name.ilike(name))
        return await self._run_and_scalar(stmt, "find_by_name")

    # --- 处理层级结构的核心方法 ---

    async def get_root_categories(self) -> List[Category]:
        """获取所有根分类（即没有父分类的顶级分类）。"""
        stmt = self._base_stmt().where(self.model.parent_id.is_(None)).order_by(self.model.name)
        return await self._run_and_scalars(stmt, "get_root_categories")

    async def get_category_tree(self) -> List[Category]:
        """
        获取完整的分类树。
        这是一个非常实用的方法，用于前端需要展示层级结构的地方，如树形选择器。
        它通过一次查询获取所有数据，然后在内存中构建树形结构，性能很高。
        """
        # query = select(self.model).options(selectinload(self.model.children)).order_by(self.model.name)
        query = select(self.model).order_by(self.model.name)
        result = await self.db.execute(query)
        all_categories = result.scalars().all()

        # 使用一个字典来快速查找节点
        category_map = {category.id: category for category in all_categories}

        # 清空所有节点的 children 列表，准备重建
        for category in all_categories:
            category.children = []

        root_categories = []
        for category in all_categories:
            if category.parent_id and category.parent_id in category_map:
                # 如果有父节点，将自己添加到父节点的 children 列表中
                parent = category_map[category.parent_id]
                parent.children.append(category)
            else:
                # 如果没有父节点，它就是一个根节点
                root_categories.append(category)

        return root_categories

    async def get_descendants_cte(self, category_id: UUID) -> List[Category]:
        """
        【企业级功能】使用递归通用表表达式(CTE)来获取一个分类的所有后代（子、孙等）。
        这是处理树形结构最高效、最强大的查询方式。
        """
        # 定义递归查询的初始部分（种子）
        category_cte = (
            select(self.model)
            .where(self.model.id == category_id)
            .cte(name="category_cte", recursive=True)
        )

        # 定义递归部分
        cte_alias = category_cte.alias()
        category_alias = self.model.__table__.alias()

        category_cte = category_cte.union_all(
            select(category_alias).where(
                category_alias.c.parent_id == cte_alias.c.id
            )
        )

        # 执行最终查询
        stmt = select(self.model).join(
            category_cte, self.model.id == category_cte.c.id
        ).where(
            category_cte.c.id != category_id  # 不包含自身
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_paged_categories(
            self, *, page: int, per_page: int, filters: Dict[str, Any], sort_by: List[str]
    ) -> PageResponse[Category]:
        """获取分类的分页列表（后台管理使用）。"""
        return await self.get_paged_list(
            page=page, per_page=per_page, filters=filters, sort_by=sort_by
        )

    async def are_ids_valid(self, ids: List[UUID]) -> bool:
        """
        高效地检查一组ID是否都存在于 category 表中。
        """
        if not ids:
            return True  # 如果传入空列表，视为有效

        # 使用 set 去重，以防传入重复ID
        unique_ids = set(ids)

        # 构建查询，只查询符合条件的ID的数量
        stmt = select(func.count(self.model.id)).where(self.model.id.in_(unique_ids))

        result = await self.db.execute(stmt)
        existing_count = result.scalar_one()

        # 如果数据库中存在的数量与我们传入的唯一ID数量相等，则所有ID都有效
        return existing_count == len(unique_ids)
