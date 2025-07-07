from fastapi import APIRouter
from app.api.routes import recipes_router, user_router, minio_router
api_router = APIRouter()
api_router.include_router(recipes_router.router, prefix="/recipes", tags=["recipes"])
api_router.include_router(user_router.router, prefix="/user", tags=["user"])
api_router.include_router(minio_router.router, prefix="/minio", tags=["minio"])