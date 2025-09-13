# app/services/recipes/unit_service.py

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy import select, func

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException
from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.recipes.recipe import Unit, RecipeIngredient
from app.repo.crud.common.base_repo import PageResponse
from app.schemas.recipes.unit_schemas import UnitCreate, UnitUpdate, UnitRead, UnitMergePayload
from app.repo.crud.recipes.unit_repo import UnitRepository
from app.services._base_service import BaseService


class UnitService(BaseService):
    def __init__(self, factory: RepositoryFactory):
        super().__init__()
        self.unit_repo: UnitRepository = factory.get_repo_by_type(UnitRepository)

    async def get_all_units(self) -> List[UnitRead]:
        """获取所有单位，用于前端选择器。"""
        units_orm = await self.unit_repo.get_all_units()
        return [UnitRead.model_validate(unit) for unit in units_orm]

    async def get_unit_by_id(self, unit_id: UUID, view_mode: str = ViewMode.ACTIVE.value) -> Unit:
        unit = await self.unit_repo.get_by_id(unit_id, view_mode=view_mode)
        if not unit:
            raise NotFoundException("单位不存在")
        return unit

    async def page_list_units(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any], view_mode: str
    ) -> PageResponse[UnitRead]:
        paged_units = await self.unit_repo.get_paged_units(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}, view_mode=view_mode
        )
        paged_units.items = [UnitRead.model_validate(item) for item in paged_units.items]
        return paged_units

    async def create_unit(self, unit_in: UnitCreate) -> Unit:
        """【事务性】创建新单位，并进行重名校验。"""
        if await self.unit_repo.find_by_name(unit_in.name):
            raise AlreadyExistsException("已存在同名单位")

        async with self.unit_repo.db.begin_nested():
            new_unit = await self.unit_repo.create(unit_in)
        return new_unit

    async def update_unit(self, unit_id: UUID, unit_in: UnitUpdate) -> Unit:
        """【事务性】更新单位，并进行重名校验。"""
        unit_to_update = await self.get_unit_by_id(unit_id)
        update_data = unit_in.model_dump(exclude_unset=True)

        if not update_data:
            return unit_to_update

        if "name" in update_data and update_data["name"].lower() != unit_to_update.name.lower():
            existing = await self.unit_repo.find_by_name(update_data["name"])
            if existing and existing.id != unit_id:
                raise AlreadyExistsException("更新失败，已存在同名单位")

        async with self.unit_repo.db.begin_nested():
            updated_unit = await self.unit_repo.update(unit_to_update, update_data)
        return updated_unit

    async def delete_unit(self, unit_id: UUID) -> None:
        """【事务性】【修改】软删除单位，并进行使用情况检查。"""
        async with self.unit_repo.db.begin_nested():
            unit_to_delete = await self.get_unit_by_id(unit_id)

            count_stmt = select(func.count(RecipeIngredient.id)).where(RecipeIngredient.unit_id == unit_id)
            usage_count = await self.unit_repo.db.scalar(count_stmt)
            if usage_count > 0:
                raise BusinessRuleException(f"无法删除，该单位正在被 {usage_count} 个菜谱配料使用")

            await self.unit_repo.soft_delete(unit_to_delete)

    async def batch_delete_units(self, unit_ids: List[UUID]) -> int:
        """【事务性】【新增】批量软删除单位，并进行使用情况检查。"""
        if not unit_ids:
            return 0
        unique_ids = list(set(unit_ids))

        async with self.unit_repo.db.begin_nested():
            if not await self.unit_repo.are_ids_valid(unique_ids):
                raise NotFoundException("一个或多个要删除的单位不存在。")

            count_stmt = select(func.count(RecipeIngredient.id)).where(RecipeIngredient.unit_id.in_(unique_ids))
            usage_count = await self.unit_repo.db.scalar(count_stmt)
            if usage_count > 0:
                raise BusinessRuleException("操作失败：选中的单位中仍有单位正在被使用，无法删除。")

            deleted_count = await self.unit_repo.soft_delete_by_ids(unique_ids)

        return deleted_count

    async def restore_units(self, unit_ids: List[UUID]) -> int:
        """【事务性】【新增】批量恢复被软删除的单位。"""
        if not unit_ids:
            return 0
        unique_ids = list(set(unit_ids))

        async with self.unit_repo.db.begin_nested():
            units_to_restore = await self.unit_repo.get_by_ids(unique_ids, view_mode=ViewMode.DELETED.value)
            if len(units_to_restore) != len(unique_ids):
                raise NotFoundException("一个或多个要恢复的单位不存在于回收站中。")

            restored_count = await self.unit_repo.restore_by_ids(unique_ids)

        return restored_count

    async def hard_delete_units(self, unit_ids: List[UUID]) -> int:
        """【事务性】【新增】批量永久删除单位（高危操作）。"""
        if not unit_ids:
            return 0
        unique_ids = list(set(unit_ids))

        async with self.unit_repo.db.begin_nested():
            units_to_delete = await self.unit_repo.get_by_ids(unique_ids, view_mode=ViewMode.DELETED.value)
            if len(units_to_delete) != len(unique_ids):
                raise NotFoundException("一个或多个要永久删除的单位不存在于回收站中。")

            # 业务规则：由于只有未被使用的单位才能被软删除，
            # 所以进入回收站的单位必定是未被使用的，可以直接进行物理删除。
            deleted_count = await self.unit_repo.hard_delete_by_ids(unique_ids)

        return deleted_count

    async def merge_units(self, payload: UnitMergePayload) -> dict:
        """【事务性】【新增】将多个源单位合并到一个目标单位。"""
        source_ids = list(set(payload.source_unit_ids))
        target_id = payload.target_unit_id

        if not source_ids:
            raise BusinessRuleException("必须提供至少一个源单位ID。")
        if target_id in source_ids:
            raise BusinessRuleException("目标单位不能是被合并的源单位之一。")

        async with self.unit_repo.db.begin_nested():
            if not await self.unit_repo.are_ids_valid(source_ids + [target_id]):
                raise NotFoundException("一个或多个指定的单位ID不存在。")

            # 1. 将所有使用 source_ids 的配料，重新映射到 target_id
            remapped_count = await self.unit_repo.remap_ingredients_to_new_unit(source_ids, target_id)
            self.logger.info(f"重新映射了 {remapped_count} 个配料到新的单位 {target_id}")

            # 2. 软删除源单位
            deleted_count = await self.unit_repo.soft_delete_by_ids(source_ids)
            self.logger.info(f"合并后软删除了 {deleted_count} 个源单位。")

        return {"merged_count": deleted_count, "remapped_ingredients": remapped_count}