from collections import Counter
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.users.user import Role
from app.repo.crud.users.user_repo import UserRepository
from app.schemas.common.page_schemas import PageResponse
from app.schemas.users.role_schemas import RoleCreate, RoleUpdate, RoleReadWithPermissions
from app.repo.crud.users.role_repo import RoleRepository
from app.repo.crud.users.permission_repo import PermissionRepository
from app.core.exceptions import NotFoundException, AlreadyExistsException, ConcurrencyConflictException, \
    BaseBusinessException
from app.services._base_service import BaseService
from app.config.config_settings.config_loader import logger


class RoleService(BaseService):
    """
    角色服务层。
    负责处理所有与角色相关的业务逻辑，包括角色与权限的关联。
    """

    def __init__(self, repo_factory: RepositoryFactory):
        super().__init__()
        self.factory = repo_factory
        self.role_repo: RoleRepository = repo_factory.get_repo_by_type(RoleRepository)
        self.permission_repo: PermissionRepository = repo_factory.get_repo_by_type(PermissionRepository)
        self.user_repo: UserRepository = repo_factory.get_repo_by_type(UserRepository)


        # --- 基础角色查询 ---

    async def get_role_by_id(self, role_id: UUID, view_mode: str = ViewMode.ACTIVE) -> Role:
        """根据ID获取角色，未找到则抛出业务异常。"""
        role = await self.role_repo.get_by_id(role_id, view_mode=view_mode)
        if not role:
            raise NotFoundException("角色不存在")
        return role

    async def get_role_with_permissions(self, role_id: UUID, view_mode: str = ViewMode.ACTIVE) -> Role:
        """获取角色及其关联的所有权限。"""
        role = await self.role_repo.get_by_id_with_permissions(role_id, view_mode=view_mode)
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
            sort_by: Optional[List[str]] = None,
            filters: Optional[Dict[str, Any]] = None,
            view_mode: str = ViewMode.ACTIVE,  # <-- 【新增】view_mode 参数
    ) -> PageResponse[RoleReadWithPermissions]:
        """
        获取角色分页列表，支持动态过滤和排序。
        (全新实现，利用 BaseRepository 的强大功能)
        """
        repo_filters = filters or {}

        # 1. 像 permission 模块一样，定义 "search" 的业务含义
        if 'search' in repo_filters and repo_filters['search']:
            search_value = repo_filters.pop('search')
            # "搜索"角色意味着对 name 和 code 两个字段进行模糊查询
            repo_filters['__or__'] = {
                'name__ilike': search_value,
                'code__ilike': search_value,
            }

        # 2. 告诉底层查询需要预加载角色的权限，避免 N+1 问题
        eager_loading_options = [
            selectinload(self.role_repo.model.permissions)
        ]

        # 3. 调用真正存在的、强大的通用分页方法
        paged_roles_orm = await self.role_repo.get_paged_list(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            filters=repo_filters,
            eager_loads=eager_loading_options,  # 传入预加载选项
            view_mode=view_mode
        )

        logger.info("获取角色分页列表，结果：{}".format(paged_roles_orm))
        # 4. 将 ORM 对象转换为 Pydantic Read 模型
        items_dto = [RoleReadWithPermissions.model_validate(r) for r in paged_roles_orm.items]

        # 5. 返回完全组装好的分页响应
        return PageResponse(
            items=items_dto,
            page=paged_roles_orm.page,
            per_page=paged_roles_orm.per_page,
            total=paged_roles_orm.total,
            total_pages=paged_roles_orm.total_pages
        )

    async def list_roles(self, skip: int = 0, limit: int = 100) -> List[Role]:
        """
        获取角色列表（支持分页）。
        """
        return await self.role_repo.list(skip=skip, limit=limit)

    async def create_role(self, role_in: RoleCreate) -> Role:
        """创建一个新角色，并原子化地关联其权限。"""


        permission_ids = role_in.permission_ids or []

        new_role_obj = None
        async with self.role_repo.db.begin_nested():
            if await self.role_repo.get_by_code(role_in.code):
                raise AlreadyExistsException(f"角色代码 '{role_in.code}' 已存在。")
            # 1. 【数据准备】获取所有待关联的 Permission ORM 对象
            permissions_to_assign = []
            if permission_ids:
                unique_ids = list(set(permission_ids))
                permissions_to_assign = await self.permission_repo.get_by_ids(unique_ids)
                if len(permissions_to_assign) != len(unique_ids):
                    raise NotFoundException("一个或多个指定的权限不存在。")

            # 2. 【内存中创建】先在内存中创建 Role 对象实例
            role_data_dict = role_in.model_dump(exclude={"permission_ids"})
            new_role_obj = Role(**role_data_dict)

            # 3. 【内存中关联】将 Permission 对象列表直接赋值给新实例的 .permissions 属性
            if permissions_to_assign:
                new_role_obj.permissions = permissions_to_assign

            # 4. 【写入】将这个构造完整的对象一次性添加到 session 中
            self.role_repo.db.add(new_role_obj)

            # 5. 【获取ID】我们需要 flush 来让 new_role_obj 获得数据库生成的 ID
            await self.role_repo.flush()

        # 6. 【返回完整对象】使用 get 方法返回一个包含了所有预加载关系的“干净”对象
        return await self.get_role_with_permissions(new_role_obj.id)

    async def update_role(self, role_id: UUID, updates: RoleUpdate) -> Role:
        role_to_update = await self.get_role_with_permissions(role_id)
        update_data = updates.model_dump(exclude_unset=True)

        new_code = update_data.get("code")
        if new_code and new_code != role_to_update.code:
            existing_role = await self.role_repo.get_by_code(new_code)
            if existing_role and existing_role.id != role_id:
                raise AlreadyExistsException(f"角色代码 '{new_code}' 已被其他角色使用。")

        try:
            async with self.role_repo.db.begin_nested():
                if "permission_ids" in update_data:
                    permission_ids = update_data.pop("permission_ids")
                    if permission_ids is not None:
                        if permission_ids and not await self.permission_repo.are_ids_valid(permission_ids):
                            raise NotFoundException("一个或多个指定的权限不存在。")
                        await self.role_repo.set_role_permissions_by_ids(role_to_update, permission_ids)

                if update_data:
                    await self.role_repo.update(role_to_update, update_data)
        except StaleDataError:
            raise ConcurrencyConflictException("操作失败，角色信息已被他人修改，请刷新后重试。")
        except Exception as e:
            raise e

        return await self.get_role_with_permissions(role_id)

    async def soft_delete_role(self, role_id: UUID) -> None:
        """软删除一个角色。"""
        role = await self.get_role_by_id(role_id)
        async with self.role_repo.db.begin_nested():
            await self.role_repo.soft_delete(role)

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

    async def soft_delete_roles(self, role_ids: List[UUID]) -> int:
        """批量软删除角色，带有前置安全检查。"""
        if not role_ids:
            return 0

        async with self.role_repo.db.begin_nested():
            # 【核心新增】从 permanent_delete_roles 中复制安全检查逻辑
            roles_in_use = await self.role_repo.get_roles_assigned_to_users(role_ids)
            if roles_in_use:
                role_names = ", ".join([role.name for role in roles_in_use])
                raise BaseBusinessException(  # 确保导入 BusinessException
                    message=f"无法删除角色 '{role_names}'，因为它们仍被分配给用户。"
                )

            # 只有在检查通过后，才执行软删除
            deleted_count = await self.role_repo.soft_delete_by_ids(role_ids)

        return deleted_count

    async def restore_roles(self, role_ids: List[UUID]) -> int:
        """批量恢复软删除的角色，带有双重冲突检查。"""
        if not role_ids:
            return 0

        unique_role_ids = list(set(role_ids))

        async with self.role_repo.db.begin_nested():
            # 1. 获取所有待恢复的角色
            roles_to_restore = await self.role_repo.get_by_ids(unique_role_ids, view_mode=ViewMode.DELETED)
            if len(roles_to_restore) != len(unique_role_ids):
                raise NotFoundException("一个或多个要恢复的角色不存在于回收站中。")

            # 2. 【核心修正】双重冲突检查
            codes_to_restore = [role.code for role in roles_to_restore]

            # 检查点 A: 待恢复的列表内部是否存在 code 冲突
            code_counts = Counter(codes_to_restore)
            internal_conflicts = [code for code, count in code_counts.items() if count > 1]
            if internal_conflicts:
                raise BaseBusinessException(
                    message=f"恢复失败！你选择的数据中包含重复的代码: {', '.join(internal_conflicts)}。一次只能恢复一个。"
                )

            # 检查点 B: 待恢复的角色是否与已存在的活跃角色冲突
            if codes_to_restore:
                conflicting_active_roles = await self.role_repo.find_active_roles_by_codes(codes_to_restore)
                if conflicting_active_roles:
                    conflicting_codes = ", ".join([role.code for role in conflicting_active_roles])
                    raise BaseBusinessException(
                        message=f"恢复失败！代码为 '{conflicting_codes}' 的角色已存在于活跃列表中。"
                    )

            # 3. 如果所有检查都通过，才执行恢复操作
            restored_count = await self.role_repo.restore_by_ids(unique_role_ids)

        return restored_count

    async def permanent_delete_roles(self, role_ids: List[UUID]) -> int:
        """批量永久删除角色，带有前置安全检查。"""
        if not role_ids:
            return 0

        deleted_count = 0
        async with self.role_repo.db.begin_nested():
            # 1. 核心安全检查：角色是否仍被使用
            roles_in_use = await self.role_repo.get_roles_assigned_to_users(role_ids)
            if roles_in_use:
                role_names = ", ".join([role.name for role in roles_in_use])
                raise BaseBusinessException(
                    message=f"无法删除角色 '{role_names}'，因为它们仍被分配给用户。"
                )

            # 2. 清理关联的权限
            await self.role_repo.clear_permissions_by_role_ids(role_ids)

            # 3. 执行物理删除
            deleted_count = await self.role_repo.hard_delete_by_ids(role_ids)

        return deleted_count

    async def merge_roles(self, source_role_ids: List[UUID], destination_role_id: UUID) -> Role:
        """
        将多个源角色合并到一个目标角色，借鉴 Tag 模块的实现。
        """
        unique_source_ids = list(set(source_role_ids))
        if not unique_source_ids:
            raise BaseBusinessException(message="必须提供至少一个源角色。")
        if destination_role_id in unique_source_ids:
            raise BaseBusinessException(message="目标角色不能是被合并的源角色之一。")

        async with self.role_repo.db.begin_nested():
            # 1. 验证所有ID都有效，并获取完整的 Role 对象（预加载权限）
            all_ids = unique_source_ids + [destination_role_id]
            # 【修正】使用 get_by_ids_with_permissions 获取带权限的对象
            roles_to_process = await self.role_repo.get_by_ids_with_permissions(all_ids)
            if len(roles_to_process) != len(all_ids):
                raise NotFoundException("一个或多个指定的角色ID不存在。")

            source_roles = [r for r in roles_to_process if r.id in unique_source_ids]
            destination_role = next(r for r in roles_to_process if r.id == destination_role_id)

            # 2. 【新增】合并权限的逻辑
            all_permission_ids = {p.id for p in destination_role.permissions}  # 目标角色原有权限
            for role in source_roles:
                all_permission_ids.update(p.id for p in role.permissions)  # 添加源角色的权限

            # 使用我们强大的 repo 方法，为目标角色设置合并后的权限全集
            await self.role_repo.set_role_permissions_by_ids(destination_role, list(all_permission_ids))

            # 3. 找到所有需要重新映射的用户
            user_ids_to_remap = await self.role_repo.get_user_ids_for_roles(unique_source_ids)

            # 4. 为这些用户添加目标角色
            if user_ids_to_remap:
                await self.user_repo.add_roles_to_users(user_ids_to_remap, [destination_role_id])

            # 5. 删除旧的 user-role 关联 (这一步现在是必须的，因为 add_roles_to_users 只添加不删除)
            await self.role_repo.delete_links_for_roles(unique_source_ids)

            # 6. 软删除源角色
            await self.role_repo.soft_delete_by_ids(unique_source_ids)

        return await self.get_role_with_permissions(destination_role_id)