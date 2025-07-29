# app/core/permissions.py

from typing import Any, Type

from app.core.exceptions import PermissionDeniedException
from app.models.base.base_model import BaseModel
from app.schemas.users.user_context import UserContext


class PermissionPolicies:
    """
    一个集中的、声明式的权限策略类。
    此类中的方法负责检查权限，如果检查失败，则直接抛出 PermissionDeniedException 异常。
    这使得 Service 层的代码可以保持干净，专注于业务逻辑。
    """

    @staticmethod
    def _get_resource_name(entity: Any) -> str:
        """一个内部辅助函数，从模型实例中获取一个通用的小写资源名称。"""
        if hasattr(entity, '__tablename__'):
            return entity.__tablename__.lower()
        return entity.__class__.__name__.lower()

    @staticmethod
    def has_permission(user: UserContext, permission: str, error_msg: str = None) -> None:
        """
        一个通用的权限码检查器。
        检查用户是否拥有特定的权限码。超级用户总是拥有所有权限。
        """
        if user.is_superuser or permission in user.permissions:
            return

        detail = error_msg or f"操作失败：缺少 '{permission}' 权限"
        raise PermissionDeniedException(detail)

    @staticmethod
    def can_create(user: UserContext, resource_name: str) -> None:
        """检查用户是否有权创建一个资源。"""
        permission_needed = f"{resource_name}:create"
        PermissionPolicies.has_permission(user, permission_needed)

    @staticmethod
    def can_update(user: UserContext, entity: Type[BaseModel], entity_name: str = "资源") -> None:
        """
        检查用户是否有权更新一个实体。
        规则：
        1. 超级用户可以。
        2. 拥有 "resource:update:any" 权限的用户可以 (例如，内容管理员)。
        3. 拥有 "resource:update:own" 权限且是实体所有者的用户可以。
        """
        if user.is_superuser:
            return

        resource = PermissionPolicies._get_resource_name(entity)
        permission_any = f"{resource}:update:any"
        permission_own = f"{resource}:update:own"

        # 检查是否有全局更新权限
        if permission_any in user.permissions:
            return

        # 检查是否有“更新自己的”权限，并且是所有者
        if hasattr(entity, 'created_by') and entity.created_by == user.id:
            if permission_own in user.permissions:
                return

        raise PermissionDeniedException(f"你没有权限更新此{entity_name}")

    @staticmethod
    def can_delete(user: UserContext, entity: Type[BaseModel], entity_name: str = "资源") -> None:
        """
        检查用户是否有权删除一个实体。
        规则与 can_update 类似。
        """
        if user.is_superuser:
            return

        resource = PermissionPolicies._get_resource_name(entity)
        permission_any = f"{resource}:delete:any"
        permission_own = f"{resource}:delete:own"

        if permission_any in user.permissions:
            return

        if hasattr(entity, 'created_by') and entity.created_by == user.id:
            if permission_own in user.permissions:
                return

        raise PermissionDeniedException(f"你没有权限删除此{entity_name}")

    # --- 示例：更复杂的、特定于业务的策略 ---
    @staticmethod
    def can_publish_recipe(user: UserContext, recipe: Any) -> None:
        """检查用户是否有权发布一篇菜谱。"""
        # 假设只有拥有 'recipe:publish' 权限的人才能发布
        PermissionPolicies.has_permission(user, "recipe:publish")

        # 还可以添加其他业务规则，例如：
        # if not recipe.cover_image_id:
        #     raise BusinessRuleException("发布失败：菜谱必须有封面图片")