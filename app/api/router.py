from fastapi import APIRouter
from app.api.routes.extra import minio_router
from app.api.routes.recipes import recipes_router
from app.api.routes.management import user_router, role_router, permission_router
from app.api.routes.auth import auth_router

api_router = APIRouter()

# recipes routers
api_router.include_router(recipes_router.router, prefix="/recipes", tags=["recipes"])

# management routers
api_router.include_router(user_router.router, prefix="/user", tags=["user"])
api_router.include_router(role_router.router, prefix="/role", tags=["role"])
api_router.include_router(permission_router.router, prefix="/permission", tags=["permission"])

# extra routers
api_router.include_router(minio_router.router, prefix="/minio", tags=["minio"])

# auth routers
api_router.include_router(auth_router.router, prefix="/auth", tags=["auth"])