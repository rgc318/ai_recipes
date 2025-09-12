# app/api/routers/tag_router.py

from types import NoneType
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.service_getters.common_service_getter import get_tag_service
from app.core.exceptions import BaseBusinessException
from app.enums.query_enums import ViewMode
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.tag_schemas import (
    TagRead,
    TagCreate,
    TagUpdate,
    TagFilterParams, BatchDeleteTagsPayload, TagMergePayload,
)
from app.services.recipes.tag_service import TagService

# 标签的查询接口对所有登录用户开放，但写操作仅限超级管理员
router = APIRouter()


@router.post(
    "/restore",
    response_model=StandardResponse[dict],
    summary="[管理员] 恢复软删除的标签"
)
async def restore_tags(
    payload: BatchDeleteTagsPayload, # 复用 BatchDeleteTagsPayload 来接收 tag_ids
    service: TagService = Depends(get_tag_service)
):
    """批量恢复一个或多个已被软删除的标签。"""
    try:
        restored_count = await service.restore_tags(payload.tag_ids)
        return response_success(
            data={"restored_count": restored_count},
            message=f"成功恢复 {restored_count} 个标签"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)


# ▼▼▼ 【核心新增】永久删除标签的 API 端点 ▼▼▼
@router.delete(
    "/permanent-delete",
    response_model=StandardResponse[dict],
    summary="[管理员] 永久删除标签（高危）"
)
async def permanent_delete_tags(
    payload: BatchDeleteTagsPayload,
    service: TagService = Depends(get_tag_service)
):
    """
    从数据库中物理删除一个或多个标签。
    这是一个不可逆的高危操作，通常只用于清理回收站。
    """
    try:
        deleted_count = await service.hard_delete_tags(payload.tag_ids)
        return response_success(
            data={"deleted_count": deleted_count},
            message=f"成功永久删除 {deleted_count} 个标签"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.post(
    "/merge",
    response_model=StandardResponse[dict],
    summary="[管理员] 合并标签"
)
async def merge_tags(
    payload: TagMergePayload,
    service: TagService = Depends(get_tag_service)
):
    """
    将一个或多个源标签合并到一个目标标签中。
    源标签的菜谱关联关系将被转移到目标标签，然后源标签将被删除。
    """
    try:
        result = await service.merge_tags(payload)
        return response_success(data=result, message="标签合并成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)


# ▼▼▼ 【核心新增】批量删除的 API 端点 ▼▼▼
@router.delete(
    "/batch",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量删除标签"
)
async def batch_delete_tags(
    payload: BatchDeleteTagsPayload,
    service: TagService = Depends(get_tag_service)
):
    """
    批量删除一个或多个标签。
    注意：如果任何一个要删除的标签仍被菜谱使用，整个操作将失败。
    """
    try:
        # 假设 Service 层有一个 batch_delete_tags 方法
        deleted_count = await service.batch_delete_tags(payload.tag_ids)
        return response_success(
            data={"deleted_count": deleted_count},
            message=f"成功删除 {deleted_count} 个标签"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)

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
    per_page: int = Query(10, ge=1, le=1000, description="每页数量"),
    sort: Optional[str] = Query("-recipe_count,name", description="排序字段 (例如: name, -recipe_count)"),
    view_mode: ViewMode = Query(ViewMode.ACTIVE, description="查看模式: active, all, deleted"),
    filter_params: TagFilterParams = Depends(),
):
    sort_by = sort.split(',') if sort else ["-recipe_count", "name"]
    filters = filter_params.model_dump(exclude_unset=True)

    if "search" in filters and filters["search"]:
        # 将前端的通用 search 参数，转换为后端的 name__ilike 精确过滤条件
        filters["name__ilike"] = filters.pop("search")

    page_data = await service.page_list_tags(
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        filters=filters,
        view_mode=view_mode.value # <-- 把这根“电线”接上
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

