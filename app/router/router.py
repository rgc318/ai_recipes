from fastapi import APIRouter
from app.api.routes import recipes
api_router = APIRouter()
api_router.include_router(recipes.router, prefix="", tags=["recipes"])