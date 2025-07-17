from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.crud.base_repo import BaseRepository
from app.models.user import Role, Permission
from app.schemas.role_schemas import RoleCreate, RoleUpdate

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

    async def get_by_id_with_permissions(self, role_id: UUID) -> Optional[Role]:
        """
        根据ID获取角色，并使用 selectinload 高效预加载其关联的所有权限。
        这是获取角色详情时避免 N+1 查询问题的最佳实践。
        """
        stmt = (
            self._base_stmt()
            .where(self.model.id == role_id)
            .options(selectinload(self.model.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

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
        await self.db.refresh(role)
        return role
