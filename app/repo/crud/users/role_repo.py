from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.enums.query_enums import ViewMode
from app.repo.crud.common.base_repo import BaseRepository
from app.models.users.user import Role, Permission, UserRole, RolePermission
from app.schemas.users.role_schemas import RoleCreate, RoleUpdate

class RoleRepository(BaseRepository[Role, RoleCreate, RoleUpdate]):
    """
    角色模型的数据仓库。
    封装了所有与 Role 表相关的数据库操作，包括其与 Permission 的关联管理。
    """
    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        super().__init__(db, Role, context)

    async def get_by_code(self, code: str) -> Optional[Role]:
        """
        根据角色的唯一代码获取角色。
        (建议使用 code 而非 name 作为唯一标识)
        """
        stmt = self._base_stmt().where(self.model.code == code)
        return await self._run_and_scalar(stmt, "get_by_code")

    async def get_by_name(self, name: str) -> Optional[Role]:
        stmt = self._base_stmt().where(self.model.name == name)
        return await self._run_and_scalar(stmt, "get_by_name")

    async def get_by_id_with_permissions(self, role_id: UUID, view_mode: str = ViewMode.ACTIVE) -> Optional[Role]:
        """
        根据ID获取角色，并使用 selectinload 高效预加载其关联的所有权限。
        这是获取角色详情时避免 N+1 查询问题的最佳实践。
        """
        stmt = (
            self._base_stmt(view_mode=view_mode)
            .where(self.model.id == role_id)
            .options(selectinload(self.model.permissions))
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_ids_with_permissions(self, role_ids: List[UUID], view_mode: str = ViewMode.ACTIVE) -> List[Role]:
        """
        根据ID列表获取角色，并预先加载每个角色的权限。
        这是 get_by_id_with_permissions 的批量版本。
        """
        if not role_ids:
            return []

        stmt = (

            # 而在更新时，我们可能需要获取任何存在的角色ID，无论其状态。

            # select(self.model)
            self._base_stmt(view_mode=view_mode)
            .where(self.model.id.in_(role_ids))
            .options(selectinload(self.model.permissions))
        )
        result = await self.db.execute(stmt)
        # 使用 .all() 获取所有结果
        return result.unique().scalars().all()
    async def add_permission_to_role(self, role: Role, permission: Permission) -> Role:
        """
        在内存中为指定角色添加一个权限。不提交事务。
        """
        if permission not in role.permissions:
            role.permissions.append(permission)
            self.db.add(role)
            await self.db.flush()
        return role

    async def remove_permission_from_role(self, role: Role, permission: Permission) -> Role:
        """
        在内存中从指定角色中移除一个权限。不提交事务。
        """
        if permission in role.permissions:
            role.permissions.remove(permission)
            self.db.add(role)
            await self.db.flush()
        return role

    async def set_role_permissions(self, role: Role, permissions: List[Permission]) -> Role:
        """
        在内存中批量设置一个角色的所有权限。不提交事务。
        """
        role.permissions = permissions
        self.db.add(role)
        await self.db.flush()
        # await self.db.refresh(role)
        return role

    # 【新增】为永久删除功能提供辅助方法
    async def get_roles_assigned_to_users(self, role_ids: List[UUID]) -> List[Role]:
        """检查给定的角色ID中，哪些仍被分配给至少一个用户。"""
        if not role_ids:
            return []
        stmt = (
            select(Role)
            .join(UserRole)
            .where(Role.id.in_(role_ids))
            .distinct()
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def clear_permissions_by_role_ids(self, role_ids: List[UUID]) -> int:
        """根据角色ID列表，物理删除 role_permission 表中的关联记录。"""
        if not role_ids:
            return 0

        stmt = delete(RolePermission).where(RolePermission.role_id.in_(role_ids))
        result = await self.db.execute(stmt)
        return result.rowcount

    # --- 【核心新增】一个更强大、更易用的权限设置方法 ---
    async def set_role_permissions_by_ids(self, role: Role, permission_ids: List[UUID]) -> Role:
        """
        根据权限ID列表，批量设置一个角色的所有权限。
        此方法封装了所有底层逻辑：ID校验、对象获取、关联更新。
        """
        permissions_to_set = []
        # 如果传入了ID列表，则查询并校验
        if permission_ids:
            unique_ids = list(set(permission_ids))

            # 从数据库中获取所有对应的 Permission 对象
            stmt = select(Permission).where(Permission.id.in_(unique_ids))
            result = await self.db.execute(stmt)
            permissions_to_set = result.scalars().all()

            # 校验是否所有ID都找到了对应的权限
            if len(permissions_to_set) != len(unique_ids):
                raise NotFoundException("一个或多个指定的权限ID不存在。")

        # 直接在内存中修改 role 对象的 .permissions 属性
        # 如果 permission_ids 为空列表，这里的 permissions_to_set 也为空列表，会清空所有权限
        role.permissions = permissions_to_set

        self.db.add(role)
        await self.db.flush()
        # 注意：这里不需要 refresh，因为 Service 层在最后会用 get_by_id... 重新查询
        return role

    async def get_user_ids_for_roles(self, role_ids: List[UUID]) -> List[UUID]:
        """获取所有分配了给定角色中任意一个的、不重复的用户ID列表。"""
        if not role_ids:
            return []
        stmt = select(UserRole.user_id).where(UserRole.role_id.in_(role_ids)).distinct()
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_links_for_roles(self, role_ids: List[UUID]) -> int:
        """根据角色ID列表，删除 user_role 表中的所有关联记录。"""
        if not role_ids:
            return 0
        stmt = delete(UserRole).where(UserRole.role_id.in_(role_ids))
        result = await self.db.execute(stmt)
        return result.rowcount

    async def find_active_roles_by_codes(self, codes: List[str]) -> List[Role]:
        """根据 code 列表，查找所有活跃的角色。"""
        if not codes:
            return []
        stmt = self._base_stmt(view_mode=ViewMode.ACTIVE).where(self.model.code.in_(codes))
        result = await self.db.execute(stmt)
        return result.scalars().all()