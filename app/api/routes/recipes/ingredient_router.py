# app/api/routers/ingredient_router.py

from types import NoneType
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.service_getters.common_service_getter import get_ingredient_service
from app.core.exceptions import BaseBusinessException
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.common.page_schemas import PageResponse
from app.schemas.recipes.ingredient_schemas import (
    IngredientRead,
    IngredientCreate,
    IngredientUpdate,
    IngredientFilterParams,
)
from app.services.recipes.ingredient_service import IngredientService

router = APIRouter()

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
):
    sort_by = sort.split(',') if sort else ["name"]
    filters = filter_params.model_dump(exclude_unset=True)

    if "name" in filters:
        filters["name__ilike"] = filters.pop("name")
    if "description" in filters:
        filters["description__ilike"] = filters.pop("description")

    page_data = await service.page_list_ingredients(
        page=page, per_page=per_page, sort_by=sort_by, filters=filters
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
    "/{ingredient_id}",
    response_model=StandardResponse[NoneType],
    status_code=status.HTTP_200_OK,
    summary="[管理员] 删除指定食材",
    # dependencies=[Depends(require_superuser)],
)
async def delete_ingredient(
    ingredient_id: UUID, service: IngredientService = Depends(get_ingredient_service)
):
    try:
        await service.delete_ingredient(ingredient_id)
        return response_success(data=None, message="食材删除成功")
    except BaseBusinessException as e:
        return response_error(message=e.message)