# app/api/routers/common/category_router.py

from types import NoneType
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.permissions import require_superuser, require_authenticated_user
from app.api.dependencies.service_getters.categories_service_getter import get_category_service # 假设已在 common_service_getter.py 中创建
from app.core.exceptions import BaseBusinessException
from app.enums.query_enums import ViewMode
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.common.category_schemas import (
    CategoryRead,
    CategoryCreate,
    CategoryUpdate,
    CategoryFilterParams,
    CategoryReadWithChildren, BatchDeleteCategoriesPayload, CategoryMergePayload,
)
from app.services.common.category_service import CategoryService

router = APIRouter()

@router.get(
    "/tree",
    response_model=StandardResponse[List[CategoryReadWithChildren]],
    summary="获取完整的分类树",
    dependencies=[Depends(require_authenticated_user)], # 普通登录用户即可获取，用于菜谱编辑器
)
async def get_category_tree(
    service: CategoryService = Depends(get_category_service)
):
    """
    获取所有分类，并以层级（树形）结构返回。
    此接口性能高，专为前端树形选择器等组件优化。
    """
    try:
        category_tree = await service.get_category_tree()
        return response_success(data=category_tree)
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.post(
    "/merge",
    response_model=StandardResponse[dict],
    summary="[管理员] 合并分类",
    dependencies=[Depends(require_superuser)],
)
async def merge_categories(
    payload: CategoryMergePayload, service: CategoryService = Depends(get_category_service)
):
    result = await service.merge_categories(payload)
    return response_success(data=result, message="分类合并成功")

@router.delete(
    "/batch",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量软删除分类",
    dependencies=[Depends(require_superuser)],
)
async def batch_delete_categories(
    payload: BatchDeleteCategoriesPayload, service: CategoryService = Depends(get_category_service)
):
    deleted_count = await service.batch_delete_categories(payload.category_ids)
    return response_success(data={"deleted_count": deleted_count}, message=f"成功删除 {deleted_count} 个分类")

@router.post(
    "/restore",
    response_model=StandardResponse[dict],
    summary="[管理员] 恢复软删除的分类",
    dependencies=[Depends(require_superuser)],
)
async def restore_categories(
    payload: BatchDeleteCategoriesPayload, service: CategoryService = Depends(get_category_service)
):
    restored_count = await service.restore_categories(payload.category_ids)
    return response_success(data={"restored_count": restored_count}, message=f"成功恢复 {restored_count} 个分类")

@router.delete(
    "/permanent-delete",
    response_model=StandardResponse[dict],
    summary="[管理员] 永久删除分类",
    dependencies=[Depends(require_superuser)],
)
async def permanent_delete_categories(
    payload: BatchDeleteCategoriesPayload, service: CategoryService = Depends(get_category_service)
):
    deleted_count = await service.hard_delete_categories(payload.category_ids)
    return response_success(data={"deleted_count": deleted_count}, message=f"成功永久删除 {deleted_count} 个分类")

@router.get(
    "/",
    response_model=StandardResponse[PageResponse[CategoryRead]],
    summary="[管理员] 分页获取分类列表",
    dependencies=[Depends(require_superuser)], # 列表管理需要超级管理员权限
)
async def list_categories_paginated(
    service: CategoryService = Depends(get_category_service),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort: Optional[str] = Query("name"),
    view_mode: ViewMode = Query(ViewMode.ACTIVE, description="查看模式"), # <--【新增】
    filter_params: CategoryFilterParams = Depends(),
):
    """
    供后台管理使用的分页、筛选、排序接口。
    """
    sort_by = sort.split(',') if sort else ["name"]
    # [核心修正] 重构过滤器构建逻辑
    query_params = filter_params.model_dump(exclude_unset=True)
    filters = {}

    # 1. 处理 name 字段为模糊搜索
    if name_query := query_params.get("name"):
        filters["name__ilike"] = name_query

    # 2. 处理其他可能的精确匹配字段
    if slug := query_params.get("slug"):
        filters["slug"] = slug  # 'slug' 默认就是精确匹配 'slug__eq'

    if parent_id := query_params.get("parent_id"):
        filters["parent_id"] = parent_id  # 'parent_id' 默认就是精确匹配
    page_data = await service.page_list_categories(
        page=page, per_page=per_page, sort_by=sort_by, filters=filters, view_mode=view_mode.value  # <--【新增】
    )
    return response_success(data=page_data)


@router.post(
    "/",
    response_model=StandardResponse[CategoryRead],
    status_code=status.HTTP_201_CREATED,
    summary="[管理员] 创建新分类",
    dependencies=[Depends(require_superuser)],
)
async def create_category(
    category_in: CategoryCreate,
    service: CategoryService = Depends(get_category_service),
):
    try:
        # 传递 current_user 以便 Service 层进行权限检查和审计记录
        new_category = await service.create_category(category_in)
        return response_success(data=CategoryRead.model_validate(new_category), message="分类创建成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.get(
    "/{category_id}",
    response_model=StandardResponse[CategoryRead],
    summary="[管理员] 获取分类详情",
    dependencies=[Depends(require_superuser)],
)
async def get_category_details(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service),
):
    try:
        category = await service.get_category_by_id(category_id)
        return response_success(data=CategoryRead.model_validate(category))
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.put(
    "/{category_id}",
    response_model=StandardResponse[CategoryRead],
    summary="[管理员] 更新指定分类",
    dependencies=[Depends(require_superuser)],
)
async def update_category(
    category_id: UUID,
    category_in: CategoryUpdate,
    service: CategoryService = Depends(get_category_service),
):
    try:
        updated_category = await service.update_category(category_id, category_in)
        return response_success(data=CategoryRead.model_validate(updated_category), message="分类更新成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.delete(
    "/{category_id}",
    response_model=StandardResponse[NoneType],
    status_code=status.HTTP_200_OK,
    summary="[管理员] 软删除指定分类",
    dependencies=[Depends(require_superuser)],
)
async def delete_category(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service),
):
    try:
        await service.delete_category(category_id)
        return response_success(data=None, message="分类删除成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)



