# app/core/permissions/recipe.py

from app.core.permissions.base_permission.base_permission import BasePolicy
from app.core.exceptions import PermissionDeniedException, BusinessRuleException
from app.schemas.users.user_context import UserContext
from app.models.recipes.recipe import Recipe


# 2. 继承时，明确指出泛型的具体类型是 Recipe
class RecipePolicy(BasePolicy[Recipe]):
    """
    专门负责处理“菜谱”权限的策略类。
    """
    ENTITY_NAME = "菜谱"

    def can_publish(self, user: UserContext, recipe: Recipe) -> None:
        """
        【模块特化逻辑】检查用户是否有权发布一篇菜谱。
        """
        permission_needed = "recipe:publish"
        if not self._has_permission(user, permission_needed):
            raise PermissionDeniedException("你没有权限发布菜谱")

        if not recipe.cover_image_id:
            raise BusinessRuleException("发布失败：菜谱必须有关联的封面图片")


# 3. 创建一个单例，方便 Service 层直接调用
recipe_policy = RecipePolicy()