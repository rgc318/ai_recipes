from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm.exc import StaleDataError

from app.db.repository_factory_auto import RepositoryFactory
from app.models.user import Role, Permission
from app.schemas.page_schemas import PageResponse
from app.schemas.role_schemas import RoleCreate, RoleUpdate
from app.db.crud.role_repo import RoleRepository
from app.db.crud.permission_repo import PermissionRepository
from app.core.exceptions import NotFoundException, AlreadyExistsException, ConcurrencyConflictException
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

        # --- 基础角色查询 ---

    async def get_role_by_id(self, role_id: UUID) -> Role:
        """根据ID获取角色，未找到则抛出业务异常。"""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundException("角色不存在")
        return role

    async def get_role_with_permissions(self, role_id: UUID) -> Role:
        """获取角色及其关联的所有权限。"""
        role = await self.role_repo.get_by_id_with_permissions(role_id)
        if not role:
            raise NotFoundException("角色不存在")
        return role

    async def get_all_roles(self) -> List[Role]:
        """
        获取所有角色列表，用于下拉框等场景。
        内置一个合理的安全上限（例如1000），防止性能问题。
        """
        # 调用底层的 list 方法，但设置一个高的、固定的 limit 作为安全保障
        return await self.role_repo.list(skip=0, limit=1000)
    async def page_list_roles(
            self,
            page: int = 1,
            per_page: int = 10,
            order_by: str = "created_at:desc",
            name: Optional[str] = None,
            code: Optional[str] = None,
    ) -> PageResponse[Role]:
        """获取角色分页列表，支持按名称或代码搜索。"""

        # 构造传递给仓库层的 filters 和 search 参数
        filters = {}
        if code:
            filters['code'] = code

        search_fields = []
        if name:
            search_fields.append('name')

        return await self.role_repo.list_with_filters(
            page=page,
            per_page=per_page,
            order_by=order_by,
            filters=filters,
            search=name,  # 将 name 作为模糊搜索
            search_fields=search_fields
        )

    async def list_roles(self, skip: int = 0, limit: int = 100) -> List[Role]:
        """
        获取角色列表（支持分页）。
        """
        return await self.role_repo.list(skip=skip, limit=limit)

    async def update_role(self, role_id: UUID, updates: RoleUpdate) -> Role:
        """更新角色信息，包括其关联的权限。具备事务原子性和乐观锁。"""
        role_to_update = await self.get_role_with_permissions(role_id)
        update_data = updates.model_dump(exclude_unset=True)

        new_code = update_data.get("code")
        if new_code and new_code != role_to_update.code:
            if await self.role_repo.get_by_code(new_code):
                raise AlreadyExistsException("角色代码已存在")

        if "permission_ids" in update_data:
            permission_ids = update_data.pop("permission_ids")
            if permission_ids is not None:
                permissions = await self.permission_repo.get_by_ids(list(set(permission_ids)))
                if len(permissions) != len(set(permission_ids)):
                    raise NotFoundException("一个或多个权限不存在")
                # 在内存中更新关系
                role_to_update.permissions = permissions

        if update_data:
            await self.role_repo.update(role_to_update, update_data)

        try:
            await self.role_repo.commit()
            await self.role_repo.refresh(role_to_update)
        except StaleDataError:
            await self.role_repo.rollback()
            raise ConcurrencyConflictException("操作失败，角色信息已被他人修改，请刷新后重试")
        except Exception as e:
            await self.role_repo.rollback()
            raise e

        return role_to_update

    async def delete_role(self, role_id: UUID) -> None:
        """软删除一个角色。"""
        role = await self.get_role_by_id(role_id)
        try:
            await self.role_repo.soft_delete(role)
            await self.role_repo.commit()
        except Exception as e:
            await self.role_repo.rollback()
            raise e

    # --- 角色与权限的关联管理 ---

    async def assign_permission_to_role(self, role_id: UUID, permission_id: UUID) -> Role:
        # 1. 获取角色和权限的实体对象
        # 注意这里 get_role_by_id 的笔误已修正
        role = await self.get_role_with_permissions(role_id)

        permission = await self.permission_repo.get_by_id(permission_id)
        if not permission:
            raise NotFoundException("权限不存在")

        # 2. 检查是否已存在，避免重复添加
        if permission in role.permissions:
            return role

        # 3. 在事务中执行操作
        try:
            updated_role = await self.role_repo.add_permission_to_role(role, permission)
            await self.role_repo.commit()
            return updated_role
        except Exception as e:
            await self.role_repo.rollback()
            raise e

    async def revoke_permission_from_role(self, role_id: UUID, permission_id: UUID) -> Role:
        """
        从角色中撤销一个权限。
        """
        # 建议使用 get_role_with_permissions 以确保权限被加载
        role = await self.get_role_with_permissions(role_id)

        # permission_repo 已在 __init__ 中定义为 self.permission_repo
        permission = await self.permission_repo.get_by_id(permission_id)
        if not permission:
            # 建议错误信息与上下文匹配
            raise NotFoundException("权限不存在")

        # 检查权限是否存在于角色中
        if permission not in role.permissions:
            return role  # 如果不存在，直接返回，无需操作

        # 【关键】添加事务控制块
        try:
            updated_role = await self.role_repo.remove_permission_from_role(role, permission)
            await self.role_repo.commit()
            return updated_role
        except Exception as e:
            await self.role_repo.rollback()
            raise e

    async def set_role_permissions(self, role_id: UUID, permission_ids: List[UUID]) -> Role:
        """【独立的业务】批量设置一个角色的所有权限。"""
        role_to_update = await self.get_role_by_id(role_id)

        permissions = []
        if permission_ids:
            unique_ids = list(set(permission_ids))
            permissions = await self.permission_repo.get_by_ids(unique_ids)
            if len(permissions) != len(unique_ids):
                raise NotFoundException("一个或多个权限不存在")

        updated_role = await self.role_repo.set_role_permissions(role_to_update, permissions)

        try:
            await self.role_repo.commit()
            return updated_role
        except Exception as e:
            await self.role_repo.rollback()
            raise e