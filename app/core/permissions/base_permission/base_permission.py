# app/core/permissions/base.py

from typing import Type, TypeVar, Generic
from app.core.exceptions import PermissionDeniedException
from app.models.base.base_model import BaseModel
from app.schemas.users.user_context import UserContext

# 1. 定义一个类型变量(泛型)，它必须是 BaseModel 或其子类
EntityType = TypeVar("EntityType", bound=BaseModel)


class BasePolicy(Generic[EntityType]):
    """
    一个标准化的、企业级的、使用泛型的权限策略基类。
    """

    @staticmethod
    def _get_resource_name_from_class(resource_class: Type[EntityType]) -> str:
        return resource_class.__tablename__.lower()

    @staticmethod
    def _get_resource_name_from_entity(entity: EntityType) -> str:
        return entity.__class__.__tablename__.lower()

    @staticmethod
    def _has_permission(user: UserContext, permission: str) -> bool:
        return user.is_superuser or permission in user.permissions

    # --- 需要“模型类”作为参数的策略 ---

    def can_list(self, user: UserContext, resource_class: Type[EntityType]) -> None:
        resource_name = self._get_resource_name_from_class(resource_class)
        permission_needed = f"{resource_name}:list"
        if not self._has_permission(user, permission_needed):
            raise PermissionDeniedException(f"你没有权限查看 {resource_name} 列表")

    def can_create(self, user: UserContext, resource_class: Type[EntityType]) -> None:
        resource_name = self._get_resource_name_from_class(resource_class)
        permission_needed = f"{resource_name}:create"
        if not self._has_permission(user, permission_needed):
            raise PermissionDeniedException(f"你没有权限创建新的 {resource_name}")

    # --- 需要“模型实例”作为参数的策略 ---

    def can_view(self, user: UserContext, entity: EntityType, entity_name: str = "资源") -> None:
        resource_name = self._get_resource_name_from_entity(entity)
        permission_needed = f"{resource_name}:list"
        if not self._has_permission(user, permission_needed):
            raise PermissionDeniedException(f"你没有权限查看此{entity_name}")

    def can_update(self, user: UserContext, entity: EntityType, entity_name: str = "资源") -> None:
        if user.is_superuser:
            return

        resource_name = self._get_resource_name_from_entity(entity)

        if self._has_permission(user, f"{resource_name}:update:any"):
            return

        if hasattr(entity, 'created_by') and entity.created_by == user.id:
            if self._has_permission(user, f"{resource_name}:update:own"):
                return

        raise PermissionDeniedException(f"你没有权限更新此{entity_name}")

    def can_delete(self, user: UserContext, entity: EntityType, entity_name: str = "资源") -> None:
        if user.is_superuser:
            return

        resource_name = self._get_resource_name_from_entity(entity)

        if self._has_permission(user, f"{resource_name}:delete:any"):
            return

        if hasattr(entity, 'created_by') and entity.created_by == user.id:
            if self._has_permission(user, f"{resource_name}:delete:own"):
                return

        raise PermissionDeniedException(f"你没有权限删除此{entity_name}")