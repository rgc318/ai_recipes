from fastapi import APIRouter
from app.api.routes import recipes_router
api_router = APIRouter()
api_router.include_router(recipes.router, prefix="", tags=["recipes"])