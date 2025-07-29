# app/api/routers/unit_router.py

from types import NoneType
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.permissions import require_superuser, require_verified_user
from app.api.dependencies.services import get_unit_service
from app.core.exceptions import BaseBusinessException
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.unit_schemas import (
    UnitRead,
    UnitCreate,
    UnitUpdate,
    UnitFilterParams,
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
    """
    【新增】获取所有可用的单位，用于前端下拉选择框等场景，不分页。
    """
    all_units = await service.get_all_units()
    return response_success(data=all_units)


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
    sort: Optional[str] = Query("name"),
    filter_params: UnitFilterParams = Depends(),
):
    """
    供后台管理使用的分页、筛选、排序接口。
    """
    sort_by = sort.split(',') if sort else ["name"]
    filters = filter_params.model_dump(exclude_unset=True)
    if "name" in filters:
        filters["name__ilike"] = filters.pop("name")

    page_data = await service.page_list_units(
        page=page, per_page=per_page, sort_by=sort_by, filters=filters
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
    summary="[管理员] 删除指定单位",
    dependencies=[Depends(require_superuser)],
)
async def delete_unit(unit_id: UUID, service: UnitService = Depends(get_unit_service)):
    try:
        await service.delete_unit(unit_id)
        return response_success(data=None, message="单位删除成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)