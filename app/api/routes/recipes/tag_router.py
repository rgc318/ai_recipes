# app/api/routers/tag_router.py

from types import NoneType
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.service_getters.common_service_getter import get_tag_service
from app.core.exceptions import BaseBusinessException
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.tag_schemas import (
    TagRead,
    TagCreate,
    TagUpdate,
    TagFilterParams,
)
from app.services.recipes.tag_service import TagService

# 标签的查询接口对所有登录用户开放，但写操作仅限超级管理员
router = APIRouter()

@router.post(
    "/",
    response_model=StandardResponse[TagRead],
    status_code=status.HTTP_201_CREATED,
    summary="[管理员] 创建新标签",
    # dependencies=[Depends(require_superuser)],
)
async def create_tag(
    tag_in: TagCreate, service: TagService = Depends(get_tag_service)
):
    try:
        new_tag = await service.create_tag(tag_in)
        return response_success(data=TagRead.model_validate(new_tag), message="标签创建成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.get(
    "/",
    response_model=StandardResponse[PageResponse[TagRead]],
    summary="分页获取标签列表",
    # dependencies=[Depends(require_verified_user)],
)
async def list_tags_paginated(
    service: TagService = Depends(get_tag_service),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(10, ge=1, le=100, description="每页数量"),
    sort: Optional[str] = Query("name", description="排序字段"),
    filter_params: TagFilterParams = Depends(),
):
    sort_by = sort.split(',') if sort else ["name"]
    filters = filter_params.model_dump(exclude_unset=True)

    if "name" in filters:
        filters["name__ilike"] = filters.pop("name")

    page_data = await service.page_list_tags(
        page=page, per_page=per_page, sort_by=sort_by, filters=filters
    )
    return response_success(data=page_data, message="获取标签列表成功")

@router.put(
    "/{tag_id}",
    response_model=StandardResponse[TagRead],
    summary="[管理员] 更新指定标签",
    # dependencies=[Depends(require_superuser)],
)
async def update_tag(
    tag_id: UUID, tag_in: TagUpdate, service: TagService = Depends(get_tag_service)
):
    try:
        updated_tag = await service.update_tag(tag_id, tag_in)
        return response_success(data=TagRead.model_validate(updated_tag), message="标签更新成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.delete(
    "/{tag_id}",
    response_model=StandardResponse[NoneType],
    status_code=status.HTTP_200_OK,
    summary="[管理员] 删除指定标签",
    # dependencies=[Depends(require_superuser)],
)
async def delete_tag(tag_id: UUID, service: TagService = Depends(get_tag_service)):
    try:
        await service.delete_tag(tag_id)
        return response_success(data=None, message="标签删除成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)