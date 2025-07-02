# app/routers/recipe_router.py

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.recipe_service import RecipeService
from app.schemas.recipe_schemas import RecipeCreate, RecipeUpdate, RecipeRead


router = APIRouter()

def get_recipe_service(session: AsyncSession = Depends(get_session)) -> RecipeService:
    return RecipeService(session)
@router.get("/", response_model=List[RecipeRead])
async def read_recipes(service: RecipeService = Depends(get_recipe_service)):
    return await service.list_recipes()


@router.get("/{recipe_id}", response_model=RecipeRead)
async def read_recipe(recipe_id: UUID, service: RecipeService = Depends(get_recipe_service)):
    recipe = await service.get_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.post("/", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def create_recipe(recipe_data: RecipeCreate, service: RecipeService = Depends(get_recipe_service)):
    created = await service.create(recipe_data)
    return created


@router.put("/{recipe_id}", response_model=RecipeRead)
async def update_recipe(
    recipe_id: UUID,
    update_data: RecipeUpdate,
    service: RecipeService = Depends(get_recipe_service)
):
    updated = await service.update(recipe_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return updated


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(recipe_id: UUID, service: RecipeService = Depends(get_recipe_service)):
    success = await service.delete(recipe_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return None  # 或者 return Response(status_code=status.HTTP_204_NO_CONTENT)
