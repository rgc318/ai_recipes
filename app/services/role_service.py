from typing import Optional, List
from uuid import UUID
from app.db.repository_factory_auto import RepositoryFactory
from app.models.user import Role, Permission
from app.schemas.role_schemas import RoleCreate, RoleUpdate
from app.db.crud.role_repo import RoleRepository
from app.db.crud.permission_repo import PermissionRepository
from app.core.exceptions import NotFoundException, AlreadyExistsException
from app.services._base_service import BaseService


class RoleService(BaseService):
    """
    角色服务层。
    负责处理所有与角色相关的业务逻辑，包括角色与权限的关联。
    """

    def __init__(self, repo_factory: RepositoryFactory):
        super().__init__()
        self.factory = repo_factory
        self.role_repo: RoleRepository = self.factory.role
        self.permission_repo: PermissionRepository = self.factory.permission

    async def create_role(self, role_in: RoleCreate) -> Role:
        """
        创建一个新角色。
        """
        existing_role = await self.role_repo.get_by_name(role_in.name)
        if existing_role:
            raise AlreadyExistsException(f"Role with name '{role_in.name}' already exists.")
        return await self.role_repo.create(role_in)

    async def get_role_by_id(self, role_id: UUID, with_permissions: bool = False) -> Role:
        """
        根据ID获取单个角色。

        Args:
            role_id: 角色的UUID。
            with_permissions: 是否同时加载该角色的所有权限信息。

        Returns:
            找到的 Role 对象。
        """
        if with_permissions:
            role = await self.role_repo.get_by_id_with_permissions(role_id)
        else:
            role = await self.role_repo.get_by_id(role_id)

        if not role:
            raise NotFoundException("Role not found.")
        return role

    async def list_roles(self, skip: int = 0, limit: int = 100) -> List[Role]:
        """
        获取角色列表（支持分页）。
        """
        return await self.role_repo.list(skip=skip, limit=limit)

    async def update_role(self, role_id: UUID, role_in: RoleUpdate) -> Role:
        """
        更新一个现有角色。
        """
        role = await self.get_role_by_id(role_id)
        if role_in.name and role_in.name != role.name:
            existing = await self.role_repo.get_by_name(role_in.name)
            if existing:
                raise AlreadyExistsException(f"Role name '{role_in.name}' is already in use.")
        return await self.role_repo.update(role, role_in)

    async def delete_role(self, role_id: UUID) -> bool:
        """
        删除一个角色。
        """
        role = await self.get_role_by_id(role_id)
        return await self.role_repo.delete(role.id)

    # --- 角色与权限的关联管理 ---

    async def assign_permission_to_role(self, role_id: UUID, permission_id: UUID) -> Role:
        """
        为角色分配一个权限。
        这是典型的服务层业务逻辑：编排对多个Repository的调用。
        """
        # 1. 获取角色和权限的实体对象，确保它们都存在
        role = await self.get_role_by_id(role_id, with_permissions=True)

        permission_repo = self.factory.permission  # 获取 PermissionRepository 实例
        permission = await permission_repo.get_by_id(permission_id)
        if not permission:
            raise NotFoundException("Permission not found.")

        # 2. 调用Repository执行关联操作
        return await self.role_repo.add_permission_to_role(role, permission)

    async def revoke_permission_from_role(self, role_id: UUID, permission_id: UUID) -> Role:
        """
        从角色中撤销一个权限。
        """
        role = await self.get_role_by_id(role_id, with_permissions=True)

        permission_repo = self.factory.permission
        permission = await permission_repo.get_by_id(permission_id)
        if not permission:
            raise NotFoundException("Permission not found.")

        return await self.role_repo.remove_permission_from_role(role, permission)

    async def set_role_permissions(self, role_id: UUID, permission_ids: List[UUID]) -> Role:
        """
        批量设置一个角色的所有权限，此操作会覆盖旧的权限列表。
        """
        role = await self.get_role_by_id(role_id)

        permission_repo = self.factory.permission
        permissions = []
        if permission_ids:
            # 批量获取所有权限对象
            permissions = await permission_repo.get_by_ids(permission_ids)
            if len(permissions) != len(permission_ids):
                raise NotFoundException("One or more permissions not found.")

        return await self.role_repo.set_role_permissions(role, permissions)

