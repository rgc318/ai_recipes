# app/models/__init__.py

# === 用户模块 ===
from app.models.user import (
    User,
    UserAuth,
    UserSavedRecipe,
    UserAIHistory,
    UserFeedback,
    UserLoginLog,
    Role,
    Permission,
    UserRole,
    RolePermission,
)

# === 菜谱模块 ===
from app.models.recipe import (
    Recipe,
    RecipeIngredient,
    Ingredient,
    Unit,
    Tag,
    RecipeTagLink,
)
