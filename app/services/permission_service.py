import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm.exc import StaleDataError

from app.db.repository_factory_auto import RepositoryFactory
from app.models.user import Permission
from app.schemas.page_schemas import PageResponse
from app.schemas.permission_schemas import PermissionCreate, PermissionUpdate
from app.db.crud.permission_repo import PermissionRepository
from app.core.exceptions import NotFoundException, AlreadyExistsException, ConcurrencyConflictException
from app.services._base_service import BaseService

logger = logging.getLogger(__name__)


class PermissionService(BaseService):
    """
    企业级权限服务层。

    负责处理所有与权限相关的业务逻辑，并确保所有写操作的事务原子性。
    该服务充分利用了 PermissionRepository 提供的高效和便利的方法。
    """

    def __init__(self, repo_factory: RepositoryFactory):
        super().__init__()
        self.factory = repo_factory
        self.permission_repo: PermissionRepository = self.factory.permission

    # --- 核心查询方法 ---

    async def get_permission_by_id(self, permission_id: UUID) -> Permission:
        """
        根据ID获取单个权限，未找到则抛出异常。
        """
        permission = await self.permission_repo.get_by_id(permission_id)
        if not permission:
            raise NotFoundException("权限未找到")
        return permission

    async def get_permission_by_code(self, code: str) -> Permission:
        """
        根据唯一代码获取单个权限，未找到则抛出异常。
        """
        permission = await self.permission_repo.get_by_code(code)
        if not permission:
            raise NotFoundException(f"代码为 '{code}' 的权限未找到")
        return permission

    async def page_list_permissions(
            self,
            page: int = 1,
            per_page: int = 10,
            order_by: str = "group:asc,name:asc",
            group: Optional[str] = None,
            search: Optional[str] = None
    ) -> PageResponse[Permission]:
        """
        获取权限的分页列表，支持按分组过滤和模糊搜索。

        Args:
            page: 页码。
            per_page: 每页数量。
            order_by: 排序字段 (e.g., 'group:asc,name:desc')。
            group: 按分组精确过滤。
            search: 在 'code', 'name', 'description' 字段中进行模糊搜索。

        Returns:
            权限的分页响应对象。
        """
        filters = {}
        if group:
            filters['group'] = group

        # 定义可以被模糊搜索的字段
        search_fields = ['code', 'name', 'description']

        return await self.permission_repo.list_with_filters(
            page=page,
            per_page=per_page,
            order_by=order_by,
            filters=filters,
            search=search,
            search_fields=search_fields
        )

    # --- 核心写操作 (带事务管理) ---

    async def create_permission(self, permission_in: PermissionCreate) -> Permission:
        """
        创建一个新的权限。

        在创建前会检查唯一代码 'code' 是否已存在。
        整个操作是事务性的。

        Raises:
            AlreadyExistsException: 如果 'code' 已被占用。
        """
        existing = await self.permission_repo.get_by_code(permission_in.code)
        if existing:
            raise AlreadyExistsException(f"权限代码 '{permission_in.code}' 已存在。")

        try:
            new_permission = await self.permission_repo.create(permission_in)
            await self.permission_repo.commit()
            return new_permission
        except Exception as e:
            await self.permission_repo.rollback()
            logger.error(f"创建权限失败: {e}")
            raise

    async def update_permission(self, permission_id: UUID, permission_in: PermissionUpdate) -> Permission:
        """
        更新一个现有的权限，具备并发控制。

        如果尝试修改 'code'，会检查新代码是否已被其他权限使用。
        整个操作是事务性的。
        """
        permission_to_update = await self.get_permission_by_id(permission_id)
        update_data = permission_in.model_dump(exclude_unset=True)

        # 如果要更新 code，检查新 code 是否已被其他权限使用
        new_code = update_data.get("code")
        if new_code and new_code != permission_to_update.code:
            existing = await self.permission_repo.get_by_code(new_code)
            if existing and existing.id != permission_id:
                raise AlreadyExistsException(f"权限代码 '{new_code}' 已被占用。")

        try:
            # 更新操作
            updated_permission = await self.permission_repo.update(permission_to_update, update_data)
            await self.permission_repo.commit()
            await self.permission_repo.refresh(updated_permission)
            return updated_permission
        except StaleDataError:
            await self.permission_repo.rollback()
            raise ConcurrencyConflictException("操作失败，权限信息已被他人修改，请刷新后重试。")
        except Exception as e:
            await self.permission_repo.rollback()
            logger.error(f"更新权限 {permission_id} 失败: {e}")
            raise

    async def delete_permission(self, permission_id: UUID) -> None:
        """
        软删除一个权限。
        这是一个安全的操作，不会物理删除数据。
        """
        permission = await self.get_permission_by_id(permission_id)
        try:
            await self.permission_repo.soft_delete(permission)
            await self.permission_repo.commit()
            logger.info(f"权限 {permission.code} (ID: {permission_id}) 已被软删除。")
        except Exception as e:
            await self.permission_repo.rollback()
            logger.error(f"软删除权限 {permission_id} 失败: {e}")
            raise

    # --- 批量与同步操作 ---

    async def sync_permissions(self, permissions_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        从一个“源数据”同步权限，批量创建不存在的权限。
        这是系统初始化或部署时确保所有必要权限存在的核心方法。

        Args:
            permissions_data: 权限字典列表，每个字典必须包含 'code'。

        Returns:
            一个包含同步结果的字典, e.g., {'total': 20, 'found': 15, 'created': 5}
        """
        total_count = len(permissions_data)
        if total_count == 0:
            return {'total': 0, 'found': 0, 'created': 0}

        try:
            all_permissions = await self.permission_repo.bulk_get_or_create(permissions_data)
            await self.permission_repo.commit()
        except Exception as e:
            await self.permission_repo.rollback()
            logger.error(f"同步权限失败: {e}")
            raise

        found_count = total_count - (len(all_permissions) - total_count)
        created_count = len(all_permissions) - found_count

        result = {'total': total_count, 'found': found_count, 'created': created_count}
        logger.info(f"权限同步完成: {result}")
        return result