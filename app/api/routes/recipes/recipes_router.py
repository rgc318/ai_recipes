# app/api/routers/recipe_router.py

from types import NoneType
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.service_getters.common_service_getter import get_recipes_service
from app.core.exceptions import BaseBusinessException
from app.core.exceptions.base_exception import PermissionDeniedException
from app.core.security.security import get_current_user
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.recipe_schemas import (
    RecipeRead,
    RecipeCreate,
    RecipeUpdate,
    RecipeFilterParams, RecipeSummaryRead,  # 我们需要为 Recipe 创建一个 FilterParams
)
from app.schemas.users.user_context import UserContext
from app.schemas.users.user_schemas import BatchDeletePayload
from app.services.recipes.recipe_service import RecipeService

# 初始化 Router
router = APIRouter(
    # dependencies=[Depends(require_verified_user)], # 所有菜谱接口都需要用户先登录
)


@router.post(
    "/",
    response_model=StandardResponse[RecipeRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建新菜谱",
)
async def create_recipe(
    recipe_in: RecipeCreate,
    service: RecipeService = Depends(get_recipes_service),
    current_user: UserContext = Depends(get_current_user),
):
    """
    创建一个新的菜谱，包括其基本信息、关联的标签和配料列表。
    """
    try:
        new_recipe_orm = await service.create_recipe(recipe_in, current_user)
        # 使用 RecipeRead DTO 来序列化返回的数据
        return response_success(
            data=RecipeRead.model_validate(new_recipe_orm), message="菜谱创建成功"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.get(
    "/",
    response_model=StandardResponse[PageResponse[RecipeSummaryRead]],
    summary="动态分页、排序和过滤菜谱列表",
)
async def list_recipes_paginated(
    service: RecipeService = Depends(get_recipes_service),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(10, ge=1, le=100, description="每页数量"),
    sort: Optional[str] = Query("-created_at", description="排序字段"),
    filter_params: RecipeFilterParams = Depends(),
    # 【优化】新增 category_id 筛选
    category_id: Optional[UUID] = Query(None, description="根据分类ID精确过滤"),
    tag_ids: Optional[List[UUID]] = Query(None, description="根据关联的标签ID列表过滤"),
    # ingredient_ids: Optional[List[UUID]] = Query(None, description="根据关联的食材ID列表过滤"), # 如果需要也可以加上
):
    """
    获取菜谱的分页列表，支持丰富的动态过滤和排序。
    此接口为公开访问，无需登录。
    """
    sort_by = sort.split(',') if sort else ["-created_at"]
    filters = filter_params.model_dump(exclude_unset=True)

    # 【优化】将所有过滤参数的预处理集中在一起
    if "title" in filters:
        filters["title__ilike"] = filters.pop("title")
    if "description" in filters:
        filters["description__ilike"] = filters.pop("description")
    if category_id:
        filters["category_id__eq"] = category_id
    if tag_ids:
        filters["tag_ids__in"] = tag_ids

    page_data = await service.page_list_recipes(
        page=page, per_page=per_page, sort_by=sort_by, filters=filters
    )
    return response_success(data=page_data, message="获取菜谱列表成功")


@router.get(
    "/{recipe_id}",
    response_model=StandardResponse[RecipeRead],
    summary="获取指定菜谱的详细信息",
)
async def get_recipe(
    recipe_id: UUID, service: RecipeService = Depends(get_recipes_service)
):
    """
    获取单个菜谱的完整信息，包括标签和配料详情。
    """
    try:
        recipe_orm = await service.get_recipe_details(recipe_id)
        return response_success(data=RecipeRead.model_validate(recipe_orm))
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.put(
    "/{recipe_id}",
    response_model=StandardResponse[RecipeRead],
    summary="更新指定菜谱",
)
async def update_recipe(
    recipe_id: UUID,
    recipe_in: RecipeUpdate,
    service: RecipeService = Depends(get_recipes_service),
    current_user: UserContext = Depends(get_current_user),
):
    """
    更新一个已存在的菜谱。
    注意：此接口会覆盖菜谱的所有标签和配料列表。
    """
    # 此处可以加入权限判断，比如只有菜谱创建者或管理员才能修改
    # if recipe_orm.created_by != current_user.id and not current_user.is_superuser:
    #     raise PermissionDeniedException()
    try:
        updated_recipe_orm = await service.update_recipe(
            recipe_id, recipe_in, current_user
        )
        return response_success(
            data=RecipeRead.model_validate(updated_recipe_orm), message="菜谱更新成功"
        )
    except PermissionDeniedException as e:
        return response_error(message=str(e))  # 返回更具体的权限错误
    except BaseBusinessException as e:
        return response_error(message=e.message)


@router.delete(
    "/{recipe_id}",
    response_model=StandardResponse[NoneType],
    status_code=status.HTTP_200_OK,
    summary="软删除指定菜谱",
)
async def delete_recipe(
    recipe_id: UUID,
    service: RecipeService = Depends(get_recipes_service),
    current_user: UserContext = Depends(get_current_user),
):
    """
    软删除一个菜谱，数据仍在数据库中，但无法通过常规接口访问。
    """
    # 此处同样可以加入权限判断
    try:
        await service.delete_recipe(recipe_id, current_user)
        return response_success(data=None, message="菜谱删除成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.delete(
    "/batch",
    summary="[管理员] 批量软删除菜谱",
    response_model=StandardResponse[dict],
)
async def batch_delete_recipes(
    payload: BatchDeletePayload, # 复用通用的批量删除Schema
    service: RecipeService = Depends(get_recipes_service),
    current_user: UserContext = Depends(get_current_user)
):
    """接收一个包含菜谱ID的数组，并批量软删除它们。"""
    try:
        # 假设 Service 层有 batch_delete_recipes 方法
        deleted_count = await service.batch_delete_recipes(
            recipe_ids=payload.ids,
            current_user=current_user
        )
        return response_success(
            data={"deleted_count": deleted_count},
            message=f"成功删除 {deleted_count} 个菜谱"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)