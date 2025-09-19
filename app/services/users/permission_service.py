import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm.exc import StaleDataError

from app.config.permission_config.permissions_enum import PERMISSIONS_CONFIG
from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.users.user import Permission
from app.schemas.common.page_schemas import PageResponse
from app.schemas.users.permission_schemas import PermissionCreate, PermissionUpdate, PermissionRead
from app.repo.crud.users.permission_repo import PermissionRepository
from app.core.exceptions import NotFoundException, AlreadyExistsException, ConcurrencyConflictException, \
    BaseBusinessException
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

    async def get_permission_by_id(self, permission_id: UUID, view_mode: str = ViewMode.ACTIVE) -> Permission:
        """根据ID获取单个权限，支持指定视图模式。"""
        permission = await self.permission_repo.get_by_id(permission_id, view_mode=view_mode)
        if not permission:
            raise NotFoundException("权限未找到")
        return permission

    async def get_permission_by_code(self, code: str, view_mode: str = ViewMode.ACTIVE) -> Permission:
        """根据唯一代码获取单个权限，支持指定视图模式。"""
        permission = await self.permission_repo.get_by_code(code, view_mode=view_mode)
        if not permission:
            raise NotFoundException(f"代码为 '{code}' 的权限未找到")
        return permission

    async def get_all_permissions(self) -> List[Permission]:
        """
        获取所有权限列表，用于下拉框等场景。
        内置一个合理的安全上限（例如1000），防止性能问题。
        """
        # 调用继承自 BaseRepository 的通用 list 方法
        return await self.permission_repo.list(skip=0, limit=1000)

    async def page_list_permissions(
            self,
            page: int = 1,
            per_page: int = 10,
            sort_by: Optional[List[str]] = None,
            filters: Optional[Dict[str, Any]] = None,
            view_mode: str = ViewMode.ACTIVE,
    ) -> PageResponse[PermissionRead]:
        """
        获取权限的分页列表，支持动态过滤和排序。
        """
        # 1. 准备传递给 repo 层的过滤器字典
        repo_filters = filters or {}

        # 2. 转换查询条件：将前端友好的模糊搜索参数转为 repo 指令
        #    例如, 将 "search=admin" 转换为对多个字段的 OR ILIKE 查询
        if 'search' in repo_filters and repo_filters['search']:
            search_value = f"%{repo_filters.pop('search')}%"
            # 使用 `__or__` 约定来告诉 BaseRepository 执行 OR 查询
            repo_filters['__or__'] = {
                'name__ilike': search_value,
                'code__ilike': search_value,
                'description__ilike': search_value,
            }

        # 对于精确匹配的字段，可以直接传递
        if 'group' in repo_filters and repo_filters['group']:
            # 明确指定为精确匹配
            repo_filters['group__like'] = repo_filters.pop('group')

        # 3. 调用 Repository 层的通用分页方法
        #    注意：PermissionRepository 继承了 BaseRepository，因此拥有 get_paged_list 方法
        paged_permissions_orm = await self.permission_repo.get_paged_list(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            filters=repo_filters,
            view_mode=view_mode
        )

        # 4. (可选) 对返回数据进行处理和转换
        #    这里我们直接将 ORM 对象列表转换为 Pydantic Read 模型列表
        items_dto = [PermissionRead.model_validate(p) for p in paged_permissions_orm.items]

        # 5. 返回符合 PageResponse[PermissionRead] 结构的数据
        return PageResponse(
            items=items_dto,
            page=paged_permissions_orm.page,
            per_page=paged_permissions_orm.per_page,
            total=paged_permissions_orm.total,
            total_pages=paged_permissions_orm.total_pages
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

    # async def sync_permissions(self, permissions_data: List[Dict[str, Any]]) -> Dict[str, int]:
    #     """
    #     从一个“源数据”同步权限，批量创建不存在的权限。
    #     这是系统初始化或部署时确保所有必要权限存在的核心方法。
    #
    #     Args:
    #         permissions_data: 权限字典列表，每个字典必须包含 'code'。
    #
    #     Returns:
    #         一个包含同步结果的字典, e.g., {'total': 20, 'found': 15, 'created': 5}
    #     """
    #     total_count = len(permissions_data)
    #     if total_count == 0:
    #         return {'total': 0, 'found': 0, 'created': 0}
    #
    #     try:
    #         all_permissions = await self.permission_repo.bulk_get_or_create(permissions_data)
    #         await self.permission_repo.commit()
    #     except Exception as e:
    #         await self.permission_repo.rollback()
    #         logger.error(f"同步权限失败: {e}")
    #         raise
    #
    #     found_count = total_count - (len(all_permissions) - total_count)
    #     created_count = len(all_permissions) - found_count
    #
    #     result = {'total': total_count, 'found': found_count, 'created': created_count}
    #     logger.info(f"权限同步完成: {result}")
    #     return result

    async def sync_permissions(self, permissions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从“源数据”同步权限，处理增、改、禁用和重新启用。"""
        async with self.permission_repo.db.begin_nested():
            result_stats = await self.permission_repo.sync_from_config(permissions_data)

        total_in_config = len(permissions_data)
        final_result = {
            'total_in_config': total_in_config,
            'created': result_stats.get('added', 0),
            'updated': result_stats.get('updated', 0),
            'disabled': result_stats.get('disabled', 0),
            'enabled': result_stats.get('enabled', 0),
        }
        logger.info(f"权限同步完成: {final_result}")
        return final_result

    async def sync_permissions_from_source(self) -> Dict[str, int]:
        """
        【模式二：后端中心】从后端配置文件 (permissions_enum.py) 同步权限。
        这是一个自给自足的方法，不依赖外部输入。
        """
        # 直接调用现有的 sync_permissions 方法，将后端配置作为数据源传入
        # 这体现了代码的高度复用
        self.logger.info("Starting permission sync from backend source file...")
        return await self.sync_permissions(PERMISSIONS_CONFIG)

    async def permanent_delete_permissions(self, permission_ids: List[UUID]) -> int:
        """
        【新增】批量永久删除权限，带有前置安全检查。
        此功能作为清理工具，用于删除已在代码中移除且不再被任何角色使用的权限。
        """
        if not permission_ids:
            return 0

        deleted_count = 0
        async with self.permission_repo.db.begin_nested():
            # 1. 业务规则：只能永久删除那些已经被禁用的（软删除的）权限
            perms_to_delete = await self.permission_repo.get_by_ids(permission_ids, view_mode=ViewMode.DELETED)
            if len(perms_to_delete) != len(set(permission_ids)):
                raise NotFoundException("一个或多个要删除的权限不存在于已禁用的权限列表中。")

            # 2. 核心安全检查：权限是否仍被任何角色使用
            perms_in_use = await self.permission_repo.get_permissions_assigned_to_roles(permission_ids)
            if perms_in_use:
                perm_codes = ", ".join([p.code for p in perms_in_use])
                raise BaseBusinessException(
                    message=f"无法删除权限 '{perm_codes}'，因为它们仍被分配给一个或多个角色。"
                )

            # 3. 清理关联关系（虽然安全检查已通过，但作为最佳实践保留）
            await self.permission_repo.clear_roles_by_permission_ids(permission_ids)

            # 4. 执行物理删除
            deleted_count = await self.permission_repo.hard_delete_by_ids(permission_ids)

        return deleted_count