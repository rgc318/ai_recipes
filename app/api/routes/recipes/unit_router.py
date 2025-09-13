# app/api/routers/unit_router.py

from types import NoneType
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.permissions import require_superuser, require_verified_user
from app.api.dependencies.service_getters.common_service_getter import get_unit_service
from app.core.exceptions import BaseBusinessException
from app.enums.query_enums import ViewMode
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.unit_schemas import (
    UnitRead,
    UnitCreate,
    UnitUpdate,
    UnitFilterParams,
    BatchDeleteUnitsPayload,
    UnitMergePayload,
)
from app.services.recipes.unit_service import UnitService

router = APIRouter()


@router.get(
    "/all",
    response_model=StandardResponse[List[UnitRead]],
    summary="获取所有单位列表",
    dependencies=[Depends(require_verified_user)],
)
async def get_all_units(service: UnitService = Depends(get_unit_service)):
    """获取所有可用的单位，用于前端下拉选择框等场景，不分页。"""
    all_units = await service.get_all_units()
    return response_success(data=all_units)


@router.delete(
    "/batch",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量软删除单位",
    dependencies=[Depends(require_superuser)],
)
async def batch_delete_units(
        payload: BatchDeleteUnitsPayload,
        service: UnitService = Depends(get_unit_service)
):
    """批量软删除一个或多个单位。如果任何单位仍被使用，整个操作将失败。"""
    try:
        deleted_count = await service.batch_delete_units(payload.unit_ids)
        return response_success(
            data={"deleted_count": deleted_count},
            message=f"成功删除 {deleted_count} 个单位"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.delete(
    "/permanent-delete",
    response_model=StandardResponse[dict],
    summary="[管理员] 永久删除单位（高危）",
    dependencies=[Depends(require_superuser)],
)
async def permanent_delete_units(
        payload: BatchDeleteUnitsPayload,
        service: UnitService = Depends(get_unit_service)
):
    """从数据库中物理删除一个或多个已软删除的单位。这是一个不可逆的高危操作。"""
    try:
        deleted_count = await service.hard_delete_units(payload.unit_ids)
        return response_success(
            data={"deleted_count": deleted_count},
            message=f"成功永久删除 {deleted_count} 个单位"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.post(
    "/merge",
    response_model=StandardResponse[dict],
    summary="[管理员] 合并单位",
    dependencies=[Depends(require_superuser)],
)
async def merge_units(
        payload: UnitMergePayload,
        service: UnitService = Depends(get_unit_service)
):
    """将一个或多个源单位合并到一个目标单位中。"""
    try:
        result = await service.merge_units(payload)
        return response_success(data=result, message="单位合并成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)
    
@router.get(
    "/",
    response_model=StandardResponse[PageResponse[UnitRead]],
    summary="[管理员] 分页获取单位列表",
    dependencies=[Depends(require_superuser)],
)
async def list_units_paginated(
        service: UnitService = Depends(get_unit_service),
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=100),
        sort: Optional[str] = Query("-ingredient_count,name", description="排序字段 (如: name, -ingredient_count)"),
        view_mode: ViewMode = Query(ViewMode.ACTIVE, description="查看模式: active, all, deleted"),
        filter_params: UnitFilterParams = Depends(),
):
    """供后台管理使用的分页、筛选、排序接口。"""
    sort_by = sort.split(',') if sort else ["-ingredient_count", "name"]
    query_filters = filter_params.model_dump(exclude_unset=True)
    search_term = query_filters.pop("name", None)

    final_filters = query_filters
    if search_term:
        final_filters["__or__"] = {
            "name__ilike": search_term,
            "abbreviation__ilike": search_term,
            "plural_name__ilike": search_term,
        }

    page_data = await service.page_list_units(
        page=page, per_page=per_page, sort_by=sort_by, filters=final_filters, view_mode=view_mode.value
    )
    return response_success(data=page_data)


@router.post(
    "/",
    response_model=StandardResponse[UnitRead],
    status_code=status.HTTP_201_CREATED,
    summary="[管理员] 创建新单位",
    dependencies=[Depends(require_superuser)],
)
async def create_unit(
        unit_in: UnitCreate, service: UnitService = Depends(get_unit_service)
):
    try:
        new_unit = await service.create_unit(unit_in)
        return response_success(data=UnitRead.model_validate(new_unit), message="单位创建成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)





@router.post(
    "/restore",
    response_model=StandardResponse[dict],
    summary="[管理员] 恢复软删除的单位",
    dependencies=[Depends(require_superuser)],
)
async def restore_units(
        payload: BatchDeleteUnitsPayload,
        service: UnitService = Depends(get_unit_service)
):
    """批量恢复一个或多个已被软删除的单位。"""
    try:
        restored_count = await service.restore_units(payload.unit_ids)
        return response_success(
            data={"restored_count": restored_count},
            message=f"成功恢复 {restored_count} 个单位"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.put(
    "/{unit_id}",
    response_model=StandardResponse[UnitRead],
    summary="[管理员] 更新指定单位",
    dependencies=[Depends(require_superuser)],
)
async def update_unit(
        unit_id: UUID, unit_in: UnitUpdate, service: UnitService = Depends(get_unit_service)
):
    try:
        updated_unit = await service.update_unit(unit_id, unit_in)
        return response_success(data=UnitRead.model_validate(updated_unit), message="单位更新成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)





@router.delete(
    "/{unit_id}",
    response_model=StandardResponse[NoneType],
    status_code=status.HTTP_200_OK,
    summary="[管理员] 软删除指定单位",
    dependencies=[Depends(require_superuser)],
)
async def delete_unit(unit_id: UUID, service: UnitService = Depends(get_unit_service)):
    """软删除指定的单位，将其移入回收站。"""
    try:
        await service.delete_unit(unit_id)
        return response_success(data=None, message="单位已移至回收站")
    except BaseBusinessException as e:
        return response_error(message=e.message)