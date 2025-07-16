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

    async def get_by_name(self, name: str) -> Optional[Role]:
        """
        根据角色的唯一名称获取角色。
        """
        stmt = select(self.model).where(
            self.model.name == name,
            self.model.is_deleted == False
        )
        return await self._run_and_scalar(stmt, "get_by_name")

    async def get_by_id_with_permissions(self, role_id: UUID) -> Optional[Role]:
        """
        根据ID获取角色，并使用 selectinload 高效预加载其关联的所有权限。
        这是获取角色详情时避免 N+1 查询问题的最佳实践。
        """
        stmt = (
            select(self.model)
            .where(self.model.id == role_id, self.model.is_deleted == False)
            .options(selectinload(self.model.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_permission_to_role(self, role: Role, permission: Permission) -> Role:
        """
        为指定角色添加一个权限。
        在操作前会检查权限是否已存在，避免重复添加。
        """
        if permission not in role.permissions:
            role.permissions.append(permission)
            self.db.add(role)
            try:
                await self.db.commit()
                await self.db.refresh(role)
            except Exception:
                await self.db.rollback()
                raise
        return role

    async def remove_permission_from_role(self, role: Role, permission: Permission) -> Role:
        """
        从指定角色中移除一个权限。
        """
        if permission in role.permissions:
            role.permissions.remove(permission)
            self.db.add(role)
            try:
                await self.db.commit()
                await self.db.refresh(role)
            except Exception:
                await self.db.rollback()
                raise
        return role

    async def set_role_permissions(self, role: Role, permissions: List[Permission]) -> Role:
        """
        批量设置一个角色的所有权限，此操作会完全覆盖该角色原有的所有权限。
        这是一个非常实用的批量操作，常用于后台管理界面的“保存”功能。
        """
        role.permissions = permissions
        self.db.add(role)
        try:
            await self.db.commit()
            await self.db.refresh(role)
        except Exception:
            await self.db.rollback()
            raise
        return role
