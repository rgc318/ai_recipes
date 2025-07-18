from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional, Dict, Any

from sqlalchemy.orm.exc import StaleDataError

from app.config import settings
from app.core.exceptions import UserNotFoundException, NotFoundException, AlreadyExistsException, \
    ConcurrencyConflictException, UnauthorizedException
from app.db.repository_factory_auto import RepositoryFactory
from app.models.user import User, Role
from app.schemas.user_schemas import UserCreate, UserUpdate, UserReadWithRoles, UserUpdateProfile
from app.core.security.password_utils import get_password_hash, verify_password
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

    async def page_list_users(
            self,
            page: int = 1,
            per_page: int = 10,
            sort_by: Optional[List[str]] = None,
            filters: Optional[Dict[str, Any]] = None,
    ) -> PageResponse[UserReadWithRoles]:
        """
        获取用户分页列表 (动态查询最终版)。
        """
        # 1. 准备传递给 repo 层的过滤器字典
        repo_filters = filters or {}

        # 2. 转换查询条件：将前端友好的查询转为后端Repo能理解的指令
        #    例如，将 "username=admin" 转换为 "username__ilike=%admin%"
        for field in ['username', 'email', 'phone', 'full_name']:
            if field in repo_filters and repo_filters[field]:
                # 从原始字典中弹出该值，并添加带操作符的新键值对
                value = repo_filters.pop(field)
                repo_filters[f'{field}__ilike'] = f"%{value}%"

        # 对于关联字段，我们约定使用 `__in`
        if 'role_ids' in repo_filters and repo_filters['role_ids']:
            value = repo_filters.pop('role_ids')
            repo_filters['role_ids__in'] = value

        # 3. 调用现在非常简洁的 repo 方法
        paged_users_orm = await self.user_repo.get_paged_users(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            filters=repo_filters,
        )

        # 4. 将 ORM 结果转换为 Pydantic Schema
        items_with_permissions = []
        for user in paged_users_orm.items:
            user_dto = UserReadWithRoles.model_validate(user)
            # 计算并填充用户的总权限集合 (这是一个很好的优化)
            all_permissions = set()
            for role in user.roles:
                for perm in role.permissions:
                    all_permissions.add(perm.code)
            user_dto.permissions = all_permissions
            items_with_permissions.append(user_dto)

        return PageResponse(
            items=items_with_permissions,
            page=paged_users_orm.page,
            per_page=paged_users_orm.per_page,
            total=paged_users_orm.total,
            total_pages=paged_users_orm.total_pages
        )

    # --- 用户操作 ---

    async def create_user(self, user_in: UserCreate) -> User:
        """创建新用户，并进行唯一性检查。"""
        # 1. 分离 role_ids 和其他用户数据
        role_ids = user_in.role_ids
        # 推荐使用 model_dump (Pydantic v2)
        user_data_dict = user_in.model_dump(exclude={"password", "role_ids"})
        if await self.user_repo.get_by_username(user_in.username):
            raise AlreadyExistsException("用户名已存在")

        if user_in.email and await self.user_repo.get_by_email(user_in.email):
            raise AlreadyExistsException("邮箱已被注册")

        if user_in.phone and await self.user_repo.get_by_phone(user_in.phone):
            raise AlreadyExistsException("电话号码已被注册")

        hashed_password = get_password_hash(user_in.password)


        user_data_dict["hashed_password"] = hashed_password

        try:
            # 【核心修改】在这里调整对象创建流程

            # 1. 在内存中创建 User 对象实例，此时它是一个“瞬态对象”
            new_user = User(**user_data_dict)

            # 2. 如果传入了 role_ids，则处理角色关联
            if role_ids:
                unique_role_ids = list(set(role_ids))
                if unique_role_ids:
                    roles = await self.role_repo.get_by_ids(unique_role_ids)
                    if len(roles) != len(unique_role_ids):
                        raise NotFoundException("一个或多个指定的角色不存在")

                    # 3. 将 Role 对象列表直接赋值给“瞬态对象”的 roles 属性
                    #    因为 new_user 还未加入 session，所以这里只是简单的 Python 列表赋值，
                    #    不会触发任何数据库懒加载。
                    new_user.roles = roles

            # 4. 将已经完全构造好的 new_user 对象添加到数据库会话中
            self.user_repo.db.add(new_user)
            await self.user_repo.flush()  # 将变更刷入数据库

            # 5. 所有操作成功，提交整个事务
            await self.user_repo.commit()

            # 6. 刷新 new_user 对象以获取最新的数据库状态（如DB默认值、触发器生成的值等）
            await self.user_repo.refresh(new_user)

            return new_user
        except Exception as e:
            # 发生任何错误，回滚事务
            await self.user_repo.rollback()
            raise e

    async def update_user(self, user_id: UUID, updates: UserUpdate) -> User:
        """
        一个功能完备且具备事务原子性的用户更新方法。
        """
        # 1. 【读取】开启一个事务，并获取"实时"的user ORM对象
        #    get_user_with_roles 确保了 user.roles 已被预加载
        user_to_update = await self.get_user_with_roles(user_id)

        # 2. 【数据准备】将传入的Pydantic模型转为字典，只包含需要更新的字段
        update_data = updates.model_dump(exclude_unset=True)

        # 3. 【业务校验】在提交前完成所有校验
        # 检查邮箱唯一性
        new_email = update_data.get("email")
        if new_email and new_email != user_to_update.email:
            if await self.user_repo.get_by_email(new_email):
                raise AlreadyExistsException("邮箱已被注册")

        # 4. 【内存中修改】分离并处理特殊字段
        # 处理密码
        if "password" in update_data and update_data["password"]:
            new_password = update_data.pop("password")
            user_to_update.hashed_password = get_password_hash(new_password)

        # 处理角色
        if "role_ids" in update_data:
            role_ids = update_data.pop("role_ids")
            # 如果 role_ids 是一个有效列表，则更新用户的角色
            if role_ids is not None:
                # 1. 获取 Role 对象列表
                roles = []
                unique_role_ids = list(set(role_ids))
                if unique_role_ids:
                    roles = await self.role_repo.get_by_ids(unique_role_ids)
                    if len(roles) != len(unique_role_ids):
                        raise NotFoundException("一个或多个角色不存在")
                    # 2. 直接在内存中修改 user.roles 属性
                    #    这正是 user_repo.set_user_roles 所做的事情
                    user_to_update.roles = roles

        # 5. 【内存中修改】使用通用的update方法更新剩下的常规字段
        if update_data:
            # 这个update方法现在只在内存中修改user_to_update对象的属性
            await self.user_repo.update(user_to_update, update_data)

        try:
            # 6. 【写入】一次性提交所有在内存中所做的修改
            await self.user_repo.commit()
            # 刷新对象以获取数据库生成的最新状态（如updated_at）
            await self.user_repo.refresh(user_to_update)
        except StaleDataError:
            await self.user_repo.rollback()
            raise ConcurrencyConflictException("操作失败，数据已被他人修改，请刷新后重试")
        except Exception as e:
            await self.user_repo.rollback()
            raise e

        return user_to_update

    async def delete_user(self, user_id: UUID) -> None:
        user = await self.get_user_by_id(user_id)
        try:
            await self.user_repo.soft_delete(user)
            await self.user_repo.commit()
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    async def lock_user(self, user_id: UUID) -> None:
        """
        锁定一个用户账户。
        【风格优化】使用公共的 repo 方法。
        """
        # 先校验用户是否存在，这是一个好习惯
        await self.get_user_by_id(user_id)

        # 这是一个独立的业务事务
        try:
            # 使用 update_by_id，这是一个公开且高效的方法
            rows_affected = await self.user_repo.update_by_id(
                user_id,
                {"is_locked": True}
            )
            if rows_affected == 0:
                # 理论上 get_user_by_id 已经检查过，但这是一个更深层次的保险
                raise UserNotFoundException()

            await self.user_repo.commit()
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    # --- 用户与角色的关联管理 ---

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> User:
        user = await self.get_user_with_roles(user_id)
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundException("角色不存在")

        # 避免重复添加
        if role in user.roles:
            return user

        try:
            updated_user = await self.user_repo.assign_role_to_user(user, role)
            await self.user_repo.commit()  # <--- 必须添加 commit
            return updated_user
        except Exception as e:
            await self.user_repo.rollback()  # <--- 必须添加 rollback
            raise e

    async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> User:
        """从用户中撤销一个角色。"""
        user = await self.get_user_with_roles(user_id)
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundException("角色不存在")

        try:
            revoke_user = await self.user_repo.revoke_role_from_user(user, role)
            await self.user_repo.commit()
            return revoke_user
        except Exception as e:
            await self.user_repo.rollback()  # <--- 必须添加 rollback
            raise e


    async def set_user_roles(self, user_id: UUID, role_ids: List[UUID], pre_fetched_user: User = None) -> User:
        """批量设置一个用户的所有角色。"""
        # 如果没有传入预查询的用户，则自己查询
        user = pre_fetched_user or await self.get_user_with_roles(user_id)

        roles = []
        if role_ids:
            unique_role_ids = list(set(role_ids))
            roles = await self.role_repo.get_by_ids(unique_role_ids)
            if len(roles) != len(unique_role_ids):
                raise NotFoundException("一个或多个角色不存在")



        try:
            # 调用 repo 层方法，该方法不 commit
            updated_user = await self.user_repo.set_user_roles(user, roles)
            await self.user_repo.commit()
            await self.user_repo.refresh(updated_user)
            return updated_user
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    # 【新增】一个专门给用户更新自己信息的方法
    async def update_profile(self, user_id: UUID, updates: UserUpdateProfile) -> User:
        """用户更新自己的个人资料，也需要在一个事务中完成。"""
        # 1. 同样先获取用户对象，以支持乐观锁
        user = await self.get_user_by_id(user_id)

        # 2. 业务校验
        update_data = updates.model_dump(exclude_unset=True)
        new_email = update_data.get("email")
        if new_email and new_email != user.email:
            if await self.user_repo.get_by_email(new_email):
                raise AlreadyExistsException("邮箱已被注册")

        # 3. 在内存中更新
        await self.user_repo.update(user, update_data)

        try:
            # 4. 统一提交
            await self.user_repo.commit()
            await self.user_repo.refresh(user)
        except StaleDataError:
            await self.user_repo.rollback()
            raise ConcurrencyConflictException("保存失败，您的个人资料可能已被系统更新，请刷新页面")
        except Exception as e:
            await self.user_repo.rollback()
            raise e

        return user

    async def change_password(self, user_id: UUID, new_plain_password: str) -> None:
        """
        为一个指定用户修改密码。这是一个独立的业务事务。
        """
        # Service层负责业务逻辑：密码必须经过哈希
        hashed_password = get_password_hash(new_plain_password)
        try:
            # Service层负责调用Repo层的基础操作
            rows_affected = await self.user_repo.update_by_id(
                user_id,
                {"hashed_password": hashed_password}
            )
            if rows_affected == 0:
                raise UserNotFoundException()  # 如果没有行被更新，说明用户不存在

            # Service层负责提交事务
            await self.user_repo.commit()
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    async def change_password_with_verification(
            self, user_id: UUID, old_plain_password: str, new_plain_password: str
    ) -> None:
        """
        【新增】用户修改自己的密码，需要验证旧密码。
        """
        user = await self.get_user_by_id(user_id)

        # 业务逻辑：验证旧密码
        if not verify_password(old_plain_password, user.hashed_password):
            raise UnauthorizedException("旧密码不正确")

        # 复用已有的、不验证旧密码的 change_password 方法
        await self.change_password(user_id, new_plain_password)

    async def reset_password_by_email(self, email: str, new_plain_password: str) -> None:
        """
        【新增】通过邮箱重置密码。
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise NotFoundException("该邮箱未注册")
        if not user.is_active:
            raise UnauthorizedException("用户账户已被禁用")

        # 直接调用 change_password 来完成密码更新和事务
        await self.change_password(user.id, new_plain_password)

    async def set_user_active_status(self, user_id: UUID, is_active: bool) -> bool:
        """
        设置用户的激活状态 (启用或禁用)。这是一个独立的业务事务。
        """
        # 先校验用户是否存在，这是一个好习惯
        await self.get_user_by_id(user_id)

        try:
            rows_affected = await self.user_repo.update_by_id(
                user_id,
                {"is_active": is_active}
            )
            await self.user_repo.commit()
            return rows_affected > 0
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    async def update_last_login(self, user_id: UUID) -> None:
        """
        更新用户最后登录时间。这是一个独立的业务事务。
        """
        try:
            await self.user_repo.update_by_id(
                user_id,
                {"last_login_at": datetime.now(timezone.utc)}
            )
            await self.user_repo.commit()
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    async def record_failed_login(self, user_id: UUID) -> None:
        """
        【新增】记录一次失败的登录尝试，并在需要时锁定用户。
        这是一个独立的业务事务。
        """
        user = await self.get_user_by_id(user_id)

        # 增加尝试次数
        new_attempts = user.login_attempts + 1

        update_data = {"login_attempts": new_attempts}

        # 检查是否达到最大尝试次数
        if new_attempts >= settings.security_settings.max_login_attempts:
            update_data["is_locked"] = True
            self.logger.warning(f"用户 {user.username} 因登录失败次数过多而被锁定。")

        try:
            # 使用高效的 update_by_id 一次性更新所有字段
            await self.user_repo.update_by_id(user.id, update_data)
            await self.user_repo.commit()
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    async def record_successful_login(self, user_id: UUID) -> None:
        """
        【新增】记录一次成功的登录，重置尝试次数并更新登录时间。
        这是一个独立的业务事务。
        """
        update_data = {
            "login_attempts": 0,
            "last_login_at": datetime.now(timezone.utc)
        }
        try:
            await self.user_repo.update_by_id(user_id, update_data)
            await self.user_repo.commit()
        except Exception as e:
            await self.user_repo.rollback()
            raise e
