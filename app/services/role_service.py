from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.db.repository_factory_auto import RepositoryFactory
from app.models.user import Role, Permission
from app.schemas.page_schemas import PageResponse
from app.schemas.role_schemas import RoleCreate, RoleUpdate, RoleReadWithPermissions
from app.db.crud.role_repo import RoleRepository
from app.db.crud.permission_repo import PermissionRepository
from app.core.exceptions import NotFoundException, AlreadyExistsException, ConcurrencyConflictException
from app.services._base_service import BaseService
from app.config.config_loader import logger


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
            sort_by: Optional[List[str]] = None,
            filters: Optional[Dict[str, Any]] = None,
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
        """
        创建一个新角色，并原子化地关联其权限。
        """
        # 1. 【业务校验】检查角色代码是否已存在
        if await self.role_repo.get_by_code(role_in.code):
            raise AlreadyExistsException(f"角色代码 '{role_in.code}' 已存在。")

        # 2. 【数据准备】将权限ID和角色的基础数据分开
        permission_ids = role_in.permission_ids
        # 使用 Pydantic 的 model_dump 方法，排除掉关联ID
        role_data_dict = role_in.model_dump(exclude={"permission_ids"})

        # --- 开始事务性操作 ---
        try:
            # 3. 【关联处理】获取所有待关联的 Permission ORM 对象
            permissions_to_assign = []
            if permission_ids:
                # 去重并校验所有权限ID的有效性
                unique_ids = list(set(permission_ids))
                permissions_to_assign = await self.permission_repo.get_by_ids(unique_ids)
                if len(permissions_to_assign) != len(unique_ids):
                    raise NotFoundException("一个或多个指定的权限不存在。")

            # 4. 【内存中创建】先在内存中创建 Role 对象实例
            new_role_obj = Role(**role_data_dict)

            # 5. 【内存中关联】如果存在要关联的权限，直接赋值给 a.permissions 属性
            if permissions_to_assign:
                new_role_obj.permissions = permissions_to_assign

            # 6. 【写入】将构造完整的 Role 对象添加到数据库会话中
            #    注意：这里我们没有调用 repo.create，而是直接操作 session，
            #    因为 repo.create 是一个更通用的方法，而这里我们需要更精细的控制。
            self.role_repo.db.add(new_role_obj)

            # 7. 【提交】一次性提交所有操作
            await self.role_repo.commit()

            # 8. 刷新对象以获取数据库生成的默认值（如id, created_at）
            await self.role_repo.refresh(new_role_obj)

            return new_role_obj
        except Exception as e:
            # 发生任何错误，回滚事务
            await self.role_repo.rollback()
            raise e
    async def update_role(self, role_id: UUID, updates: RoleUpdate) -> Role:
        """
        【全新强化版】更新角色信息，包括其关联的权限。
        具备事务原子性和完整的并发控制。
        """
        # 1. 【读取】在事务开始前，获取需要被更新的、带有最新版本号的 Role 对象
        #    get_role_with_permissions 确保了 role.permissions 已被预加载
        role_to_update = await self.get_role_with_permissions(role_id)

        # 2. 【数据准备】将传入的 Pydantic 模型转为字典，只包含需要更新的字段
        update_data = updates.model_dump(exclude_unset=True)

        # --- 开始事务性操作 ---
        try:
            # 3. 【业务校验】在提交前，完成所有业务规则的校验
            # 检查角色代码唯一性
            new_code = update_data.get("code")
            if new_code and new_code != role_to_update.code:
                existing_role = await self.role_repo.get_by_code(new_code)
                if existing_role and existing_role.id != role_id:
                    raise AlreadyExistsException(f"角色代码 '{new_code}' 已被其他角色使用。")

            # 4. 【内存中修改】分离并处理需要特殊操作的字段 (权限)
            if "permission_ids" in update_data:
                permission_ids = update_data.pop("permission_ids")

                # 只有当 permission_ids 是一个有效列表时才进行处理
                # (允许传入 null 或 [] 来清空权限)
                if permission_ids is not None:
                    permissions_to_set = []
                    unique_ids = list(set(permission_ids))
                    if unique_ids:
                        # 校验所有权限ID的有效性
                        permissions_to_set = await self.permission_repo.get_by_ids(unique_ids)
                        if len(permissions_to_set) != len(unique_ids):
                            raise NotFoundException("一个或多个指定的权限不存在。")

                    # 直接在内存中修改 role 对象的 a.permissions 属性
                    # 这得益于我们之前预加载了权限，不会触发额外的数据库查询
                    role_to_update.permissions = permissions_to_set

            # 5. 【内存中修改】使用通用的 update 方法更新剩下的常规字段
            #    注意：这个 update 方法只修改内存中的对象属性，并将其加入会话
            if update_data:
                await self.role_repo.update(role_to_update, update_data)

            # 6. 【写入】一次性提交所有在内存中所做的修改
            #    所有操作（基础信息更新、权限关联变更）将作为一个原子操作被提交
            await self.role_repo.commit()

            # 7. 刷新对象以获取数据库生成的最新状态（如 updated_at 和新版本号）
            await self.role_repo.refresh(role_to_update)

        except StaleDataError:
            # 只有在 commit 阶段才会真正检查版本号，如果冲突则抛出 StaleDataError
            await self.role_repo.rollback()
            raise ConcurrencyConflictException("操作失败，角色信息已被他人修改，请刷新后重试。")
        except Exception as e:
            # 捕获其他所有异常并回滚
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