from fastapi import APIRouter
from app.api.routes.extra import file_router, file_management_router
from app.api.routes.recipes import recipes_router, tag_router, ingredient_router, unit_router
from app.api.routes.management import user_router, role_router, permission_router
from app.api.routes.auth import auth_router
from app.api.routes.common import category_router

api_router = APIRouter()

# recipes routers
api_router.include_router(recipes_router.router, prefix="/recipes", tags=["recipes"])

# management routers
api_router.include_router(user_router.router, prefix="/user", tags=["user"])
api_router.include_router(role_router.router, prefix="/role", tags=["role"])
api_router.include_router(permission_router.router, prefix="/permission", tags=["permission"])

# extra routers
api_router.include_router(file_router.router, prefix="/file", tags=["file"])
api_router.include_router(file_management_router.router, prefix="/file_management", tags=["file_management"])

# auth routers
api_router.include_router(auth_router.router, prefix="/auth", tags=["auth"])
api_router.include_router(tag_router.router, prefix="/tags", tags=["tags"])
api_router.include_router(ingredient_router.router, prefix="/ingredient", tags=["ingredient"])
api_router.include_router(unit_router.router, prefix="/units", tags=["units"])
api_router.include_router(category_router.router, prefix="/categories", tags=["categories"])