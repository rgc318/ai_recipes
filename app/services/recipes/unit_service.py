# app/services/units/unit_service.py

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select, func

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipes.recipe import Unit, RecipeIngredient
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.unit_schemas import UnitCreate, UnitUpdate, UnitRead
from app.repo.crud.recipes.unit_repo import UnitRepository
from app.services._base_service import BaseService


class UnitService(BaseService):
    def __init__(self, factory: RepositoryFactory):
        super().__init__()
        self.unit_repo: UnitRepository = factory.get_repo_by_type(UnitRepository)

    async def get_all_units(self) -> List[UnitRead]:
        """【新增】获取所有单位，用于前端选择器。"""
        units_orm = await self.unit_repo.get_all_units()
        return [UnitRead.model_validate(unit) for unit in units_orm]

    async def get_unit_by_id(self, unit_id: UUID) -> Unit:
        unit = await self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise NotFoundException("单位不存在")
        return unit

    async def page_list_units(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any]
    ) -> PageResponse[UnitRead]:
        paged_units_orm = await self.unit_repo.get_paged_units(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}
        )
        paged_units_orm.items = [UnitRead.model_validate(item) for item in paged_units_orm.items]
        return paged_units_orm

    async def create_unit(self, unit_in: UnitCreate) -> Unit:
        if await self.unit_repo.find_by_name(unit_in.name):
            raise AlreadyExistsException("已存在同名单位")

        try:
            new_unit = await self.unit_repo.create(unit_in)
            await self.unit_repo.commit()
            return new_unit
        except Exception as e:
            await self.unit_repo.rollback()
            raise e

    async def update_unit(self, unit_id: UUID, unit_in: UnitUpdate) -> Unit:
        unit_to_update = await self.get_unit_by_id(unit_id)
        update_data = unit_in.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"].lower() != unit_to_update.name.lower():
            existing = await self.unit_repo.find_by_name(update_data["name"])
            if existing and existing.id != unit_id:
                raise AlreadyExistsException("更新失败，已存在同名单位")
        try:
            updated_unit = await self.unit_repo.update(unit_to_update, update_data)
            await self.unit_repo.commit()
            return updated_unit
        except Exception as e:
            await self.unit_repo.rollback()
            raise e

    async def delete_unit(self, unit_id: UUID) -> None:
        await self.get_unit_by_id(unit_id)

        count_stmt = select(func.count(RecipeIngredient.id)).where(RecipeIngredient.unit_id == unit_id)
        usage_count = await self.unit_repo.db.scalar(count_stmt)
        if usage_count > 0:
            raise BusinessRuleException(f"无法删除，该单位正在被 {usage_count} 个菜谱配料使用")

        try:
            unit_to_delete = await self.get_unit_by_id(unit_id)  # Re-fetch for the session
            await self.unit_repo.delete(unit_to_delete)
            await self.unit_repo.commit()
        except Exception as e:
            await self.unit_repo.rollback()
            raise e