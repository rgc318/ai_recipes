from typing import Optional, List
from uuid import UUID
from app.db.repository_factory_auto import RepositoryFactory
from app.models.user import Permission
from app.schemas.permission_schemas import PermissionCreate, PermissionUpdate
from app.db.crud.permission_repo import PermissionRepository
from app.core.exceptions import NotFoundException, AlreadyExistsException
from app.services._base_service import BaseService


class PermissionService(BaseService):
    """
    权限服务层。
    负责处理所有与权限相关的业务逻辑。
    """

    def __init__(self, repo_factory: RepositoryFactory):
        super().__init__()
        self.factory = repo_factory
        self.permission_repo: PermissionRepository = self.factory.permission

    async def create_permission(self, permission_in: PermissionCreate) -> Permission:
        """
        创建一个新的权限。

        在创建前会检查同名权限是否已存在，避免重复。

        Args:
            permission_in: 创建权限所需的数据。

        Returns:
            新创建的 Permission 对象。

        Raises:
            AlreadyExistsException: 如果同名权限已存在。
        """
        existing_permission = await self.permission_repo.get_by_name(permission_in.name)
        if existing_permission:
            raise AlreadyExistsException(f"Permission with name '{permission_in.name}' already exists.")

        return await self.permission_repo.create(permission_in)

    async def get_permission_by_id(self, permission_id: UUID) -> Permission:
        """
        根据ID获取单个权限。

        Args:
            permission_id: 权限的UUID。

        Returns:
            找到的 Permission 对象。

        Raises:
            NotFoundException: 如果权限未找到。
        """
        permission = await self.permission_repo.get_by_id(permission_id)
        if not permission:
            raise NotFoundException("Permission not found.")
        return permission

    async def list_permissions(self, skip: int = 0, limit: int = 100) -> List[Permission]:
        """
        获取权限列表（支持分页）。
        """
        return await self.permission_repo.list(skip=skip, limit=limit)

    async def update_permission(self, permission_id: UUID, permission_in: PermissionUpdate) -> Permission:
        """
        更新一个现有的权限。
        """
        permission = await self.get_permission_by_id(permission_id)

        # 如果要更新名称，检查新名称是否已被其他权限使用
        if permission_in.name and permission_in.name != permission.name:
            existing = await self.permission_repo.get_by_name(permission_in.name)
            if existing:
                raise AlreadyExistsException(f"Permission name '{permission_in.name}' is already in use.")

        return await self.permission_repo.update(permission, permission_in)

    async def delete_permission(self, permission_id: UUID) -> bool:
        """
        删除一个权限。
        """
        permission = await self.get_permission_by_id(permission_id)
        return await self.permission_repo.delete(permission.id)

