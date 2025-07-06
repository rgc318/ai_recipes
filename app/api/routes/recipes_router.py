# app/routers/recipe_router.py

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_response import response_success, response_error
from app.db.session import get_session
from app.services.recipe_service import RecipeService
from app.schemas.recipe_schemas import RecipeCreate, RecipeUpdate, RecipeRead
from app.core.response_codes import ResponseCodeEnum
from app.core.api_response import StandardResponse

router = APIRouter()

def get_recipe_service(session: AsyncSession = Depends(get_session)) -> RecipeService:
    return RecipeService(session)

# === List Recipes ===
@router.get(
    "/",
    response_model=StandardResponse[List[RecipeRead]]
)
async def read_recipes(service: RecipeService = Depends(get_recipe_service)):
    recipes = await service.list_recipes()
    return response_success(data=recipes)


# === Get Recipe by ID ===
@router.get(
    "/{recipe_id}",
    response_model=StandardResponse[RecipeRead]
)
async def read_recipe(recipe_id: UUID, service: RecipeService = Depends(get_recipe_service)):
    recipe = await service.get_by_id(recipe_id)
    if not recipe:
        return response_error(code=ResponseCodeEnum.NOT_FOUND, message="Recipe not found", http_status=status.HTTP_404_NOT_FOUND)
    return response_success(data=recipe)


# === Create Recipe ===
@router.post(
    "/",
    response_model=StandardResponse[RecipeRead],
    status_code=status.HTTP_201_CREATED
)
async def create_recipe(recipe_data: RecipeCreate, service: RecipeService = Depends(get_recipe_service)):
    created = await service.create(recipe_data)
    return response_success(
        data=created,
        code=ResponseCodeEnum.CREATED,
        message="Recipe created successfully",
        http_status=status.HTTP_201_CREATED
    )


# === Update Recipe ===
@router.put(
    "/{recipe_id}",
    response_model=StandardResponse[RecipeRead]
)
async def update_recipe(
    recipe_id: UUID,
    update_data: RecipeUpdate,
    service: RecipeService = Depends(get_recipe_service)
):
    updated = await service.update(recipe_id, update_data)
    if not updated:
        return response_error(code=ResponseCodeEnum.NOT_FOUND, message="Recipe not found", http_status=status.HTTP_404_NOT_FOUND)
    return response_success(data=updated, message="Recipe updated successfully")


# === Delete Recipe ===
@router.delete(
    "/{recipe_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK
)
async def delete_recipe(recipe_id: UUID, service: RecipeService = Depends(get_recipe_service)):
    success = await service.delete(recipe_id)
    if not success:
        return response_error(code=ResponseCodeEnum.NOT_FOUND, message="Recipe not found", http_status=status.HTTP_404_NOT_FOUND)
    return response_success(code=ResponseCodeEnum.NO_CONTENT, message="Recipe deleted successfully", data=None)
