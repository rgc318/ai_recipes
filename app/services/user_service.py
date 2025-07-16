from uuid import UUID
from typing import List, Optional

from app.core.exceptions import UserNotFoundException, NotFoundException, AlreadyExistsException
from app.db.repository_factory_auto import RepositoryFactory
from app.models.user import User, Role
from app.schemas.user_schemas import UserCreate, UserUpdate, UserReadWithRoles
from app.core.security.password_utils import get_password_hash
from app.db.crud.user_repo import UserRepository
from app.db.crud.role_repo import RoleRepository
from app.db.crud.base_repo import PageResponse
from app.services._base_service import BaseService


class UserService(BaseService):
    """
    用户服务层。
    负责处理所有与用户、角色、权限相关的核心业务逻辑。
    """

    def __init__(self, repo_factory: RepositoryFactory):
        super().__init__()
        self.factory = repo_factory
        # 假设你的工厂通过类型获取 repo
        self.user_repo: UserRepository = repo_factory.get_repo_by_type(UserRepository)
        self.role_repo: RoleRepository = repo_factory.get_repo_by_type(RoleRepository)

    # --- 基础用户查询 ---

    async def get_user_by_id(self, user_id: UUID) -> User:
        """根据ID获取用户，未找到则抛出业务异常。"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException()
        return user

    async def get_user_by_username(self, username: str) -> User:
        """根据用户名获取用户，未找到则抛出业务异常。"""
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise UserNotFoundException()
        return user

    async def get_user_by_email(self, email: str) -> User:
        """根据邮箱获取用户，未找到则抛出业务异常。"""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFoundException()
        return user

    async def get_user_with_roles(self, user_id: UUID) -> User:
        """获取用户及其关联的角色和权限，用于权限验证。"""
        user = await self.user_repo.get_by_id_with_roles_permissions(user_id)
        if not user:
            raise UserNotFoundException()
        return user

    # --- 用户列表 ---

    async def list_users(
            self,
            page: int = 1,
            per_page: int = 10,
            order_by: str = "created_at:desc",
            search: Optional[str] = None,
            role_ids: Optional[List[UUID]] = None,
            is_active: Optional[bool] = None,
    ) -> PageResponse[UserReadWithRoles]:
        """获取用户分页列表，封装了复杂的查询逻辑。"""
        return await self.user_repo.get_paged_users(
            page=page, per_page=per_page, order_by=order_by,
            search=search, role_ids=role_ids, is_active=is_active
        )

    # --- 用户操作 ---

    async def create_user(self, user_in: UserCreate) -> User:
        """创建新用户，并进行唯一性检查。"""
        if await self.user_repo.get_by_username(user_in.username):
            raise AlreadyExistsException("用户名已存在")

        if user_in.email and await self.user_repo.get_by_email(user_in.email):
            raise AlreadyExistsException("邮箱已被注册")

        hashed_password = get_password_hash(user_in.password)
        # 推荐使用 model_dump (Pydantic v2)
        user_data = user_in.model_dump(exclude={"password"})
        user_data["hashed_password"] = hashed_password

        return await self.user_repo.create(user_data)

    async def update_user(self, user_id: UUID, updates: UserUpdate) -> User:
        """更新用户信息。"""
        # 【修正】先获取用户实体，再将实体传递给 repo 的 update 方法
        existing_user = await self.get_user_by_id(user_id)

        if updates.email and updates.email != existing_user.email:
            if await self.user_repo.get_by_email(updates.email):
                raise AlreadyExistsException("邮箱已被注册")

        return await self.user_repo.update(user_id, updates)

    async def delete_user(self, user_id: UUID) -> bool:
        """软删除一个用户。"""
        await self.get_user_by_id(user_id)  # 确保用户存在
        return await self.user_repo.soft_delete(user_id)

    async def lock_user(self, user_id: UUID) -> bool:
        """
        锁定一个用户账户。
        【修正】重构此方法以提高代码复用性和一致性。
        """
        await self.get_user_by_id(user_id)  # 确保用户存在
        return await self.user_repo._update_single_field(user_id, "is_locked", True)

    # --- 用户与角色的关联管理 ---

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> User:
        """为用户分配一个角色。"""
        user = await self.get_user_with_roles(user_id)
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundException("角色不存在")

        return await self.user_repo.assign_role_to_user(user, role)

    async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> User:
        """从用户中撤销一个角色。"""
        user = await self.get_user_with_roles(user_id)
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundException("角色不存在")

        return await self.user_repo.revoke_role_from_user(user, role)

    async def set_user_roles(self, user_id: UUID, role_ids: List[UUID]) -> User:
        """批量设置一个用户的所有角色。"""
        user = await self.get_user_with_roles(user_id)

        roles = []
        if role_ids:
            # 【修正】使用更健壮的 set() 来处理可能重复的 role_ids
            unique_role_ids = list(set(role_ids))
            # 假设你的 BaseRepository 中有一个 get_by_ids 方法
            roles = await self.role_repo.get_by_ids(unique_role_ids)
            if len(roles) != len(unique_role_ids):
                raise NotFoundException("一个或多个角色不存在")

        return await self.user_repo.set_user_roles(user, roles)
