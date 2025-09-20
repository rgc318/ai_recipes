# app/api/routers/ingredient_router.py

from types import NoneType
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.service_getters.common_service_getter import get_ingredient_service
from app.core.exceptions import BaseBusinessException
from app.enums.query_enums import ViewMode
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.ingredient_schemas import (
    IngredientRead,
    IngredientCreate,
    IngredientUpdate,
    IngredientFilterParams, BatchActionIngredientsPayload, IngredientMergePayload,
)
from app.services.recipes.ingredient_service import IngredientService

router = APIRouter()

# ========================================================
# == 【新增】管理与生命周期接口 ==
# ========================================================

@router.post(
    "/restore",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量恢复食材"
)
async def restore_ingredients(
    payload: BatchActionIngredientsPayload,
    service: IngredientService = Depends(get_ingredient_service)
):
    """从回收站中批量恢复一个或多个食材。"""
    try:
        restored_count = await service.restore_ingredients(payload)
        return response_success(
            data={"restored_count": restored_count},
            message=f"成功恢复 {restored_count} 个食材"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.delete(
    "/permanent-delete",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量永久删除食材（高危）"
)
async def permanent_delete_ingredients(
    payload: BatchActionIngredientsPayload,
    service: IngredientService = Depends(get_ingredient_service)
):
    """从数据库中物理删除一个或多个食材。这是一个不可逆的高危操作。"""
    try:
        deleted_count = await service.permanent_delete_ingredients(payload)
        return response_success(
            data={"deleted_count": deleted_count},
            message=f"成功永久删除 {deleted_count} 个食材"
        )
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.post(
    "/merge",
    response_model=StandardResponse[IngredientRead],
    summary="[管理员] 合并食材"
)
async def merge_ingredients(
    payload: IngredientMergePayload,
    service: IngredientService = Depends(get_ingredient_service)
):
    """将一个或多个源食材合并到一个目标食材中。"""
    try:
        merged_ingredient = await service.merge_ingredients(payload)
        return response_success(data=merged_ingredient, message="食材合并成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.post(
    "/",
    response_model=StandardResponse[IngredientRead],
    status_code=status.HTTP_201_CREATED,
    summary="[管理员] 创建新食材",
    # dependencies=[Depends(require_superuser)],
)
async def create_ingredient(
    ingredient_in: IngredientCreate, service: IngredientService = Depends(get_ingredient_service)
):
    try:
        new_ingredient = await service.create_ingredient(ingredient_in)
        return response_success(data=IngredientRead.model_validate(new_ingredient), message="食材创建成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.get(
    "/",
    response_model=StandardResponse[PageResponse[IngredientRead]],
    summary="分页获取食材列表",
    # dependencies=[Depends(require_verified_user)],
)
async def list_ingredients_paginated(
    service: IngredientService = Depends(get_ingredient_service),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(10, ge=1, le=100, description="每页数量"),
    sort: Optional[str] = Query("name", description="排序字段"),
    filter_params: IngredientFilterParams = Depends(),
    view_mode: ViewMode = Query(ViewMode.ACTIVE, description="查看模式: active, all, deleted"),
):
    sort_by = sort.split(',') if sort else ["name"]
    filters = filter_params.model_dump(exclude_unset=True)

    # 【核心重构】处理 search 参数
    # 1. 从字典中安全地弹出 search 的值
    search_term = filters.pop("search", None)

    # 2. 如果存在 search_term，则构建一个 __or__ 查询
    if search_term:
        # 这个特殊的 "__or__" 键会被我们 BaseRepository 中的
        # _apply_dynamic_filters 方法识别并处理
        filters["__or__"] = {
            "name__ilike": f"%{search_term}%",
            "description__ilike": f"%{search_term}%"
        }


    page_data = await service.page_list_ingredients(
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        filters=filters,
        view_mode=view_mode
    )
    return response_success(data=page_data, message="获取食材列表成功")


@router.put(
    "/{ingredient_id}",
    response_model=StandardResponse[IngredientRead],
    summary="[管理员] 更新指定食材",
    # dependencies=[Depends(require_superuser)],
)
async def update_ingredient(
    ingredient_id: UUID, ingredient_in: IngredientUpdate, service: IngredientService = Depends(get_ingredient_service)
):
    try:
        updated_ingredient = await service.update_ingredient(ingredient_id, ingredient_in)
        return response_success(data=IngredientRead.model_validate(updated_ingredient), message="食材更新成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)

@router.delete(
    "/", # [修改] 改为批量接口
    response_model=StandardResponse[dict],
    summary="[管理员] 批量软删除食材"
)
async def soft_delete_ingredients(
    payload: BatchActionIngredientsPayload,
    service: IngredientService = Depends(get_ingredient_service)
):
    """根据ID列表，将一个或多个食材移入回收站。"""
    try:
        deleted_count = await service.soft_delete_ingredients(payload)
        return response_success(data={"deleted_count": deleted_count}, message="批量软删除成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)



# 【新增】单个软删除接口，提供便利性
@router.delete(
    "/{ingredient_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="[管理员] 软删除单个食材"
)
async def soft_delete_single_ingredient(
    ingredient_id: UUID,
    service: IngredientService = Depends(get_ingredient_service)
):
    """将单个食材移入回收站。"""
    try:
        # 复用批量删除的 service 方法
        payload = BatchActionIngredientsPayload(ingredient_ids=[ingredient_id])
        await service.soft_delete_ingredients(payload)
        return response_success(data=None, message="食材已移入回收站")
    except BaseBusinessException as e:
        return response_error(message=e.message)