# app/core/permissions/recipe.py

from app.core.permissions.base_permission.base_permission import BasePolicy
from app.core.exceptions import PermissionDeniedException, BusinessRuleException
from app.models.common.category_model import Category
from app.schemas.users.user_context import UserContext


# 2. 继承时，明确指出泛型的具体类型是 Category
class CategoryPolicy(BasePolicy[Category]):
    """
    专门负责处理“分类”权限的策略类。
    """
    ENTITY_NAME = "分类"

    def can_publish(self, user: UserContext, recipe: Category) -> None:
        """
        【模块特化逻辑】检查用户是否有权发布一篇分类。
        """
        permission_needed = "category:publish"
        if not self._has_permission(user, permission_needed):
            raise PermissionDeniedException("你没有权限发布分类")


# 3. 创建一个单例，方便 Service 层直接调用
category_policy = CategoryPolicy()