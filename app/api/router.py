from fastapi import APIRouter
from app.api.routes.extra import file_router, file_management_router
from app.api.routes.recipes import recipes_router, tag_router, ingredient_router, unit_router
from app.api.routes.management import user_router, role_router, permission_router
from app.api.routes.auth import auth_router
from app.api.routes.common import category_router

api_router = APIRouter()

# 将所有路由配置定义在一个列表中
# 每个元素都是一个包含 router, prefix, 和 tags 的字典
routers_to_include = [
    # recipes routers
    {"router": recipes_router.router, "prefix": "/recipes", "tags": ["recipes"]},
    {"router": tag_router.router, "prefix": "/tags", "tags": ["tags"]},
    {"router": ingredient_router.router, "prefix": "/ingredients", "tags": ["ingredients"]},
    {"router": unit_router.router, "prefix": "/units", "tags": ["units"]},

    # management routers
    {"router": user_router.router, "prefix": "/user", "tags": ["user"]},
    {"router": role_router.router, "prefix": "/role", "tags": ["role"]},
    {"router": permission_router.router, "prefix": "/permission", "tags": ["permission"]},

    # extra routers
    {"router": file_router.router, "prefix": "/file", "tags": ["file"]},
    {"router": file_management_router.router, "prefix": "/file_management", "tags": ["file_management"]},

    # auth routers
    {"router": auth_router.router, "prefix": "/auth", "tags": ["auth"]},

    # common routers
    {"router": category_router.router, "prefix": "/categories", "tags": ["categories"]},
]

# 使用一个循环来包含所有路由 ✨
for route_config in routers_to_include:
    api_router.include_router(**route_config)

# 现在，你只需要在 routers_to_include 列表中添加新的字典即可