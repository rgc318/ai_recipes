from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(recipes.router, prefix="", tags=["recipes"])