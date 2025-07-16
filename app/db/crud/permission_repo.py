from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.crud.base_repo import BaseRepository
from app.models.user import Permission
from app.schemas.permission_schemas import PermissionCreate, PermissionUpdate

class PermissionRepository(BaseRepository[Permission, PermissionCreate, PermissionUpdate]):
    """
    权限模型的数据仓库。
    封装了所有与 Permission 表相关的数据库操作。
    """
    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        super().__init__(db, Permission, context)

    async def get_by_name(self, name: str) -> Optional[Permission]:
        """
        根据权限的唯一名称获取权限。
        这是一个常用方法，用于在创建或分配权限前检查其是否存在。

        Args:
            name: 权限的名称 (e.g., 'order:create').

        Returns:
            找到的 Permission 对象或 None.
        """
        stmt = select(self.model).where(
            self.model.name == name,
            self.model.is_deleted == False
        )
        return await self._run_and_scalar(stmt, "get_by_name")
