from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.models.recipe import Recipe
from sqlmodel import select

router = APIRouter()
@router.get("/", response_model = list[Recipe])
async def get_recipes(session: AsyncSession = Depends(get_session)):
    statement = select(Recipe)
    results = await session.execute(statement)
    recipes = results.scalars().all()
    return recipes