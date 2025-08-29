# app/api/routers/common/category_router.py

from types import NoneType
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.permissions import require_superuser, require_authenticated_user
from app.api.dependencies.service_getters.categories_service_getter import get_category_service # 假设已在 common_service_getter.py 中创建
from app.core.exceptions import BaseBusinessException
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.common.category_schemas import (
    CategoryRead,
    CategoryCreate,
    CategoryUpdate,
    CategoryFilterParams,
    CategoryReadWithChildren,
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
    filter_params: CategoryFilterParams = Depends(),
):
    """
    供后台管理使用的分页、筛选、排序接口。
    """
    sort_by = sort.split(',') if sort else ["name"]
    filters = filter_params.model_dump(exclude_unset=True)

    page_data = await service.page_list_categories(
        page=page, per_page=per_page, sort_by=sort_by, filters=filters
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
    summary="[管理员] 删除指定分类",
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