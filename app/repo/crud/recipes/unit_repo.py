# app/repo/crud/unit_repo.py

from typing import List, Optional, Dict, Any

from sqlalchemy import func, select, update, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.crud.common.base_repo import BaseRepository, PageResponse
from app.models.recipes.recipe import Unit, RecipeIngredient
from app.schemas.recipes.unit_schemas import UnitCreate, UnitUpdate, UnitRead


class UnitRepository(BaseRepository[Unit, UnitCreate, UnitUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[Dict[str, Any]] = None):
        super().__init__(db=db, model=Unit, context=context)

    async def find_by_name(self, name: str) -> Optional[Unit]:
        """根据名称查找单位（大小写不敏感），用于防止重名。"""
        stmt = self._base_stmt().where(self.model.name.ilike(name))
        return await self._run_and_scalar(stmt, "find_by_name")

    async def get_all_units(self) -> List[Unit]:
        """【新增】获取所有未被软删除的单位，按名称排序。"""
        stmt = self._base_stmt().order_by(self.model.name.asc())
        return await self._run_and_scalars(stmt, "get_all_units")

    async def get_paged_units(
            self, *, page: int, per_page: int, filters: Dict[str, Any], sort_by: List[str], view_mode: str
    ) -> PageResponse:
        """
        获取单位的分页列表，并附带每个单位关联的配料数量。
        """
        ingredient_count_col = func.count(RecipeIngredient.id).label("ingredient_count")

        # 1. 构建基础的JOIN和GROUP BY查询
        stmt = (
            select(self.model, ingredient_count_col)
            .outerjoin(RecipeIngredient, self.model.id == RecipeIngredient.unit_id)
            .group_by(self.model.id)
        )

        # 2. 调用父类的 get_paged_list，并传入我们预构建的 statement
        #    这样可以复用父类的过滤、排序、计数和分页逻辑
        paged_response = await self.get_paged_list(
            page=page,
            per_page=per_page,
            filters=filters,
            sort_by=sort_by,
            view_mode=view_mode,
            stmt_in=stmt,  # 传入预处理过的 statement
            sort_map={'ingredient_count': ingredient_count_col},
            return_scalars=False
        )

        # 3. 父类返回的是 (ORM, count) 元组，我们需要将其处理成 DTO
        processed_items = []
        for unit_orm, count in paged_response.items:
            # 1. 先将数据库模型对象(unit_orm)转换为响应DTO(UnitRead)
            unit_dto = UnitRead.model_validate(unit_orm)

            # 2. 现在可以安全地给 DTO 的额外字段赋值了
            unit_dto.ingredient_count = count if count is not None else 0

            processed_items.append(unit_dto)

        paged_response.items = processed_items
        return paged_response

    async def remap_ingredients_to_new_unit(self, source_unit_ids: List[UUID], target_unit_id: UUID) -> int:
        """
        将使用源单位的配料，全部更新为使用目标单位。
        这是一个高效的批量更新操作。
        """
        if not source_unit_ids:
            return 0

        stmt = (
            update(RecipeIngredient)
            .where(RecipeIngredient.unit_id.in_(source_unit_ids))
            .values(unit_id=target_unit_id)
        )
        result = await self.db.execute(stmt)
        return result.rowcount