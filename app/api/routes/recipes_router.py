from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, status, Query
from app.services.recipe_service import RecipeService
from app.api.dependencies.services import get_recipes_service
from app.schemas.recipe_schemas import RecipeCreate, RecipeUpdate, RecipeRead
from app.core.api_response import response_success, response_error
from app.core.response_codes import ResponseCodeEnum
from app.core.api_response import StandardResponse

router = APIRouter()

# === List Recipes (分页+搜索) ===
@router.get(
    "/",
    response_model=StandardResponse[List[RecipeRead]],
    summary="获取菜谱列表（分页）",
)
async def read_recipes(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, le=100),
    search: str = Query("", alias="q"),
    service: RecipeService = Depends(get_recipes_service),
):
    recipes = await service.list_recipes_paginated(page=page, per_page=per_page, search=search)
    return response_success(data=recipes)


# === Get Recipe by ID ===
@router.get(
    "/{recipe_id}",
    response_model=StandardResponse[RecipeRead],
    summary="获取菜谱详情",
)
async def read_recipe(recipe_id: UUID, service: RecipeService = Depends(get_recipes_service)):
    recipe = await service.get_by_id(recipe_id)
    if not recipe:
        return response_error(ResponseCodeEnum.NOT_FOUND, "Recipe not found", status.HTTP_404_NOT_FOUND)
    return response_success(data=recipe)


# === Create Recipe ===
@router.post(
    "/",
    response_model=StandardResponse[RecipeRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建菜谱",
)
async def create_recipe(
    recipe_data: RecipeCreate,
    service: RecipeService = Depends(get_recipes_service),
    user_id: UUID = None,  # ✨ 可接入 Auth 系统，获取当前用户
):
    created = await service.create(recipe_data, created_by=user_id)
    return response_success(
        data=created,
        code=ResponseCodeEnum.CREATED,
        message="Recipe created successfully",
        http_status=status.HTTP_201_CREATED,
    )


# === Update Recipe ===
@router.put(
    "/{recipe_id}",
    response_model=StandardResponse[RecipeRead],
    summary="更新菜谱",
)
async def update_recipe(
    recipe_id: UUID,
    update_data: RecipeUpdate,
    service: RecipeService = Depends(get_recipes_service),
    user_id: UUID = None,
):
    updated = await service.update(recipe_id, update_data, updated_by=user_id)
    if not updated:
        return response_error(ResponseCodeEnum.NOT_FOUND, "Recipe not found", status.HTTP_404_NOT_FOUND)
    return response_success(data=updated, message="Recipe updated successfully")


# === Delete Recipe ===
@router.delete(
    "/{recipe_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="删除菜谱",
)
async def delete_recipe(
    recipe_id: UUID,
    service: RecipeService = Depends(get_recipes_service),
    user_id: UUID = None,
):
    success = await service.delete(recipe_id, deleted_by=user_id)
    if not success:
        return response_error(ResponseCodeEnum.NOT_FOUND, "Recipe not found", status.HTTP_404_NOT_FOUND)
    return response_success(code=ResponseCodeEnum.NO_CONTENT, message="Recipe deleted successfully", data=None)
