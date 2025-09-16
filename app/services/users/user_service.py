import os
import uuid
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from fastapi import Depends, UploadFile
from sqlalchemy.orm.exc import StaleDataError

from app.config import settings
from app.core.exceptions import UserNotFoundException, NotFoundException, AlreadyExistsException, \
    ConcurrencyConflictException, UnauthorizedException, PermissionDeniedException
from app.enums.query_enums import ViewMode
from app.models.files.file_record import FileRecord
from app.repo.crud.file.file_record_repo import FileRecordRepository
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.users.user import User
from app.schemas.file.file_record_schemas import FileRecordCreate, FileRecordUpdate
from app.schemas.file.file_schemas import AvatarLinkDTO
from app.schemas.users import user_context
from app.schemas.users.user_context import UserContext
from app.schemas.users.user_schemas import UserCreate, UserUpdate, UserReadWithRoles, UserUpdateProfile
from app.core.security.password_utils import get_password_hash, verify_password
from app.repo.crud.users.user_repo import UserRepository
from app.repo.crud.users.role_repo import RoleRepository
from app.repo.crud.common.base_repo import PageResponse
from app.services._base_service import BaseService
if TYPE_CHECKING:
    from app.services.file.file_record_service import FileRecordService
    from app.services.file.file_service import FileService


class UserService(BaseService):
    """
    用户服务层。
    负责处理所有与用户、角色、权限相关的核心业务逻辑。
    """

    def __init__(
            self,
            repo_factory: RepositoryFactory,
            file_service: "FileService" = Depends(),
            file_record_service: "FileRecordService" = Depends(),
    ):
        super().__init__()
        self.factory = repo_factory
        self.file_service = file_service
        self.file_record_service = file_record_service
        self.user_repo: UserRepository = repo_factory.get_repo_by_type(UserRepository)
        self.role_repo: RoleRepository = repo_factory.get_repo_by_type(RoleRepository)

    # --- 基础用户查询 ---

    # --- 【新增】辅助方法：动态填充 URL ---
    def _set_full_avatar_url(self, user_orm: User) -> User:
        """
        为一个 User ORM 对象实例丰富动态数据，如 avatar_url。
        注意：这个方法直接修改并返回传入的 ORM 对象。
        """
        if user_orm.avatar_url:  # 如果用户有关联的头像 object_name
            client = self.file_service.factory.get_client_by_profile("user_avatars")
            # 直接在 ORM 对象实例上附加一个新属性
            user_orm.avatar_url = client.build_final_url(user_orm.avatar_url)
        return user_orm

    async def get_user_by_id(self, user_id: UUID) -> User:
        """根据ID获取用户，未找到则抛出业务异常。"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException()
        # return self._set_full_avatar_url(user)
        return user

    async def get_user_by_username(self, username: str) -> User:
        """根据用户名获取用户，未找到则抛出业务异常。"""
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise UserNotFoundException()
        # return self._set_full_avatar_url(user)
        return user

    async def get_user_by_email(self, email: str) -> User:
        """根据邮箱获取用户，未找到则抛出业务异常。"""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UserNotFoundException()
        # return self._set_full_avatar_url(user)
        return user

    async def get_user_with_roles(self, user_id: UUID) -> User:
        """获取用户及其关联的角色和权限，用于权限验证。"""
        user = await self.user_repo.get_by_id_with_roles_permissions(user_id)
        if not user:
            raise UserNotFoundException()
        # return self._set_full_avatar_url(user)
        return user

    # =================================================================
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心修改点 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # 重构 page_list_users 方法，使其职责更清晰
    # =================================================================
    async def page_list_users(
            self,
            page: int = 1,
            per_page: int = 10,
            sort_by: Optional[List[str]] = None,
            filters: Optional[Dict[str, Any]] = None,
            view_mode: str = ViewMode.ACTIVE,
    ) -> PageResponse[UserReadWithRoles]:
        """
        获取用户分页列表。
        此方法现在将过滤参数的构造完全委托给上层(Router)，
        自身只负责调用数据层和处理返回的业务数据。
        """
        # 1. 直接调用 UserRepository 中已经封装好的分页方法
        #    Service 层不再关心 `filters` 字典内部是如何构造的。
        paged_users_orm = await self.user_repo.get_paged_users(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            filters=filters or {},
            view_mode=view_mode
        )

        # 2. 【核心业务逻辑】对从数据层获取的原始数据进行处理和丰富
        items_with_permissions = []
        for user in paged_users_orm.items:
            # 2.1 将 ORM 对象转换为 Pydantic DTO
            user_dto = UserReadWithRoles.model_validate(user)

            # 2.2 聚合计算用户的总权限集合，这是一个非常有价值的业务逻辑
            all_permissions = set()
            for role in user.roles:
                for perm in role.permissions:
                    all_permissions.add(perm.code)
            user_dto.permissions = list(all_permissions)  # 返回列表更符合JSON标准

            items_with_permissions.append(user_dto)

        # 3. 返回符合标准分页响应结构的数据
        return PageResponse(
            items=items_with_permissions,
            page=paged_users_orm.page,
            per_page=paged_users_orm.per_page,
            total=paged_users_orm.total,
            total_pages=paged_users_orm.total_pages
        )

    # =================================================================

    # --- 用户操作 ---

    async def create_user(self, user_in: UserCreate) -> User:
        """创建新用户，并进行唯一性检查。"""
        # 1. 分离 role_ids 和其他用户数据
        role_ids = user_in.role_ids
        avatar_file_id = user_in.avatar_file_record_id
        # 推荐使用 model_dump (Pydantic v2)
        user_data_dict = user_in.model_dump(exclude={"password", "role_ids", "avatar_file_record_id"})
        if await self.user_repo.get_by_username(user_in.username):
            raise AlreadyExistsException("用户名已存在")

        if user_in.email and await self.user_repo.get_by_email(user_in.email):
            raise AlreadyExistsException("邮箱已被注册")

        if user_in.phone and await self.user_repo.get_by_phone(user_in.phone):
            raise AlreadyExistsException("电话号码已被注册")

        hashed_password = get_password_hash(user_in.password)


        user_data_dict["hashed_password"] = hashed_password

        # 2. 初始化将在多个作用域中使用的变量
        new_user: Optional[User] = None
        file_record: Optional[FileRecord] = None
        permanent_path: Optional[str] = None
        temp_path: Optional[str] = None

        async with self.user_repo.db.begin_nested():
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

            if avatar_file_id:
                file_record_repo = self.factory.get_repo_by_type(FileRecordRepository)
                file_record = await file_record_repo.get_by_id(avatar_file_id)

                if not file_record or getattr(file_record, 'is_associated', False):
                    raise NotFoundException("指定的头像文件无效或已被使用。")

                # 1. 准备路径信息，但不执行移动
                temp_path = file_record.object_name
                filename = os.path.basename(temp_path)
                permanent_path = f"avatars/{new_user.id}/{filename}"

                # 2. 更新数据库记录（仍在事务中）
                new_user.avatar_url = permanent_path
                await self.file_record_service.update_file_record(
                    record_id=file_record.id,
                    record_update=FileRecordUpdate(
                        object_name=permanent_path,
                        is_associated=True
                    ),
                    commit=False  # 【重要】确保它加入我们的大事务
                )



        # --- 阶段二: 外部非事务性操作 ---
        # 只有在数据库事务成功后才执行
        if permanent_path and temp_path:
            try:
                # 只有在数据库成功提交后，才执行不可逆的文件移动
                await self.file_service.move_file(
                    source_key=temp_path,
                    destination_key=permanent_path,
                    profile_name="user_avatars"
                )
            except Exception as move_error:
                # 记录严重错误，因为此时数据库已更新但文件移动失败
                self.logger.critical(
                    f"CRITICAL: User {new_user.id} DB created/updated, but failed to move avatar from {temp_path} to {permanent_path}. Error: {move_error}")
                # 这里可以触发一个后台任务来重试移动，或者发出警报

        await self.user_repo.refresh(new_user)
        return new_user

    async def update_user(self, user_id: UUID, updates: UserUpdate) -> User:
        """
        一个功能完备且具备事务原子性的用户更新方法。
        """
        user_to_update = await self.get_user_with_roles(user_id)
        update_data = updates.model_dump(exclude_unset=True)

        # 业务校验（这部分可以在事务外，也可以在事务内，事务外更好）
        new_email = update_data.get("email")
        if new_email and new_email != user_to_update.email:
            if await self.user_repo.exists_by_field(new_email, "email"):  # 使用更高效的 exists_by_field
                raise AlreadyExistsException("邮箱已被注册")

        new_phone = update_data.get("phone")
        if new_phone and new_phone != user_to_update.phone:
            if await self.user_repo.exists_by_field(new_phone, "phone"):  # 使用更高效的 exists_by_field
                raise AlreadyExistsException("该手机号已被注册")

        try:
            # 【核心修正】将所有修改操作放入事务块中
            async with self.user_repo.db.begin_nested():
                # 4. 【内存中修改】分离并处理特殊字段
                if "password" in update_data and update_data["password"]:
                    new_password = update_data.pop("password")
                    user_to_update.hashed_password = get_password_hash(new_password)

                if "role_ids" in update_data:
                    role_ids = update_data.pop("role_ids")
                    if role_ids is not None:
                        roles = []
                        unique_role_ids = list(set(role_ids))
                        if unique_role_ids:
                            roles = await self.role_repo.get_by_ids(unique_role_ids)  # 建议使用不带 permission 的 get_by_ids
                            if len(roles) != len(unique_role_ids):
                                raise NotFoundException("一个或多个角色不存在")
                        user_to_update.roles = roles

                # 5. 【内存中修改】使用通用的update方法更新剩下的常规字段
                if update_data:
                    await self.user_repo.update(user_to_update, update_data)

        except StaleDataError:
            # 【核心修正】保留对并发冲突异常的捕获
            raise ConcurrencyConflictException("操作失败，数据已被他人修改，请刷新后重试")
        except Exception as e:
            # 其他异常由全局处理器处理，这里只管抛出
            self.logger.error(f"更新用户失败: {e}")
            raise e

        # refresh 操作应该在事务成功后执行
        complete_user = await self.user_repo.get_by_id_with_roles_permissions(user_id)
        if not complete_user:
            # 这是一个理论上的边缘情况，但做好防御
            raise UserNotFoundException("Failed to reload user after update.")

        return complete_user

    async def delete_user(self, user_id: UUID) -> bool:
        # 【核心修改】在检查用户是否存在时，使用 view_mode='all' 来查找所有用户
        user = await self.user_repo.get_by_id(user_id, view_mode=ViewMode.ALL.value)
        if not user:
            # 如果在所有用户中都找不到，才真正抛出异常
            raise UserNotFoundException()

        # 【可选】你甚至可以增加一个检查，防止重复删除
        if user.is_deleted:
            # 如果用户已经在回收站了，可以直接返回成功，或者抛出一个 spécifiques 错误
            self.logger.info(f"用户 {user.username} 已在回收站中，无需重复删除。")
            return  True

        try:
            async with self.user_repo.db.begin_nested():
                await self.user_repo.clear_roles_by_user_ids([user_id])
                await self.user_repo.soft_delete_by_ids([user_id])
                return True
        except Exception as e:
            self.logger.error(f"删除用户失败：{e}")
            return False
            raise e

    async def batch_delete_users(self, user_ids: List[UUID], current_user: UserContext) -> int:
        """
        批量删除用户，并包含核心业务安全校验。
        """
        # 1. 业务规则校验：禁止用户删除自己
        if current_user.id in user_ids:
            raise UnauthorizedException("不能删除自己的账户")

        # 2. 业务规则校验：非超级管理员不能删除超级管理员
        if not current_user.is_superuser:
            # 先查询出将要被删除的用户信息
            users_to_delete = await self.user_repo.get_by_ids(user_ids)
            for user in users_to_delete:
                if user.is_superuser:
                    raise UnauthorizedException(f"权限不足，无法删除超级管理员用户: {user.username}")

        # 3. 执行数据库操作
        async with self.user_repo.db.begin_nested():
            await self.user_repo.clear_roles_by_user_ids(user_ids)
            # 调用我们在 Repository 中创建的新方法
            deleted_count = await self.user_repo.soft_delete_by_ids(user_ids)

        return deleted_count


    async def lock_user(self, user_id: UUID) -> None:
        """锁定一个用户账户。"""
        await self.get_user_by_id(user_id)  # 校验用户存在

        try:
            # async with self.user_repo.db.begin(): # 开启一个自动事务块
            # SQLAlchemy < 2.0 or different setup might be:
            async with self.user_repo.db.begin_nested() if self.user_repo.db.is_active else self.user_repo.db.begin() as transaction:
                rows_affected = await self.user_repo.update_by_id(
                    user_id,
                    {"is_locked": True}
                )
            if rows_affected == 0:
                # 即使 get_user_by_id 检查过，这也能防止在极小的竞争条件下用户被删除
                raise UserNotFoundException()
            # 退出 'with' 块时，如果没异常就自动 commit 了
        except Exception as e:
            # 这里甚至可以不需要 rollback 调用，因为 with 块会自动处理
            # 只需要记录日志并重新抛出即可
            self.logger.error(f"Failed to lock user {user_id}: {e}")
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

        async with self.user_repo.db.begin_nested():
            updated_user = await self.user_repo.assign_role_to_user(user, role)

        return updated_user


    async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> User:
        """从用户中撤销一个角色。"""
        user = await self.get_user_with_roles(user_id)
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundException("角色不存在")

        async with self.user_repo.db.begin_nested():
            revoke_user = await self.user_repo.revoke_role_from_user(user, role)

        return revoke_user



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



        async with self.user_repo.db.begin_nested():
            # 调用 repo 层方法，该方法不 commit
            updated_user = await self.user_repo.set_user_roles(user, roles)

            await self.user_repo.refresh(updated_user)
        return updated_user


    # 【新增】一个专门给用户更新自己信息的方法
    async def update_profile(self, user_id: UUID, updates: UserUpdateProfile) -> User:
        """用户更新自己的个人资料，也需要在一个事务中完成。"""
        user = await self.get_user_by_id(user_id)
        update_data = updates.model_dump(exclude_unset=True)

        new_email = update_data.get("email")
        if new_email and new_email != user.email:
            if await self.user_repo.exists_by_field(new_email, "email"):
                raise AlreadyExistsException("邮箱已被注册")

        try:
            # 【核心修正】将 update 操作移入事务块
            async with self.user_repo.db.begin_nested():
                await self.user_repo.update(user, update_data)

        except StaleDataError:
            # 【核心修正】保留并发冲突检查
            raise ConcurrencyConflictException("保存失败，您的个人资料可能已被系统更新，请刷新页面")
        except Exception as e:
            self.logger.error(f"更新个人资料失败: {e}")
            raise e

        await self.user_repo.refresh(user)
        return user

    async def change_password(self, user_id: UUID, new_plain_password: str) -> None:
        hashed_password = get_password_hash(new_plain_password)
        try:
            async with self.user_repo.db.begin_nested():
                rows_affected = await self.user_repo.update_by_id(
                    user_id,
                    {"hashed_password": hashed_password}
                )
                if rows_affected == 0:
                    raise UserNotFoundException()
        except Exception as e:
            # 记录日志并重新抛出，让上层处理
            self.logger.error(f"Failed to change password for user {user_id}: {e}")
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

        if old_plain_password == new_plain_password:
            raise UnauthorizedException("新密码不能和旧密码相同")
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

        async with self.user_repo.db.begin_nested():
            rows_affected = await self.user_repo.update_by_id(
                user_id,
                {"is_active": is_active}
            )

        return rows_affected > 0


    async def update_last_login(self, user_id: UUID) -> None:
        """
        更新用户最后登录时间。这是一个独立的业务事务。
        """
        async with self.user_repo.db.begin_nested():
            await self.user_repo.update_by_id(
                user_id,
                {"last_login_at": datetime.now(timezone.utc)}
            )

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

        async with self.user_repo.db.begin_nested():
            # 使用高效的 update_by_id 一次性更新所有字段
            await self.user_repo.update_by_id(user.id, update_data)


    async def record_successful_login(self, user_id: UUID) -> None:
        """
        【新增】记录一次成功的登录，重置尝试次数并更新登录时间。
        这是一个独立的业务事务。
        """
        update_data = {
            "login_attempts": 0,
            "last_login_at": datetime.now(timezone.utc)
        }
        async with self.user_repo.db.begin_nested():
            await self.user_repo.update_by_id(user_id, update_data)


    async def update_avatar(self, user_id: UUID, upload_file: UploadFile) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException()

        old_avatar_object_name = user.avatar_url
        upload_result = None

        # --- 阶段一: 上传新文件到云存储 (外部操作) ---
        try:
            upload_result = await self.file_service.upload_user_avatar(
                file=upload_file, user_id=str(user_id)
            )
        except Exception as e:
            self.logger.error(f"Avatar upload failed for user {user_id}: {e}")
            raise

        # --- 阶段二: 数据库事务 ---
        try:
            async with self.user_repo.db.begin_nested():  # 使用自动事务块
                # 1. (软)删除旧的 FileRecord
                if old_avatar_object_name:
                    await self._cleanup_old_avatar_records(old_avatar_object_name)

                # 2. 创建新的 FileRecord
                await self.file_record_service.register_uploaded_file(
                    object_name=upload_result.object_name,
                    original_filename=upload_file.filename,
                    file_size=upload_result.file_size,
                    content_type=upload_result.content_type,
                    profile_name="user_avatars",
                    uploader_context=UserContext(id=user_id),  # 假设可以这样构建
                    etag=upload_result.etag,
                    commit=False  # 确保加入大事务
                )

                # 3. 更新 User 对象
                user.avatar_url = upload_result.object_name
                self.user_repo.db.add(user)

        except Exception as e:
            self.logger.error(f"Failed to update avatar DB records for user {user_id}: {e}")
            # 尝试清理刚刚上传的新文件，避免产生孤儿文件
            await self.file_service.delete_file(upload_result.object_name, profile_name="user_avatars")
            raise e

        # --- 阶段三: 事务成功后，清理旧的物理文件 (外部清理) ---
        if old_avatar_object_name:
            try:
                await self.file_service.delete_file(old_avatar_object_name, profile_name="user_avatars")
            except Exception as e:
                self.logger.error(
                    f"CRITICAL: DB updated for user {user_id}, "
                    f"but failed to delete old avatar file {old_avatar_object_name}. Error: {e}"
                )

        await self.user_repo.refresh(user)
        return user

    async def _cleanup_old_avatar_records(self, old_avatar_object_name: str):
        """
        【职责更明确】一个私有方法，只负责清理与旧头像相关的【数据库记录】。
        它不包含 commit，以便被调用者纳入其自身的事务。
        """
        if not old_avatar_object_name:
            return

        file_record_repo = self.factory.get_repo_by_type(FileRecordRepository)
        await file_record_repo.soft_delete_by_object_name(old_avatar_object_name)

    async def link_new_avatar(self, user_id: UUID, avatar_dto: AvatarLinkDTO, user_context: UserContext) -> User:
        """
        原子化地关联一个已通过预签名URL上传的头像（使用 begin_nested 优化）。
        """
        # 1. 获取用户信息，这部分逻辑在事务之外，完全不变
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundException()

        old_avatar_name = user.avatar_url
        new_avatar_name = avatar_dto.object_name

        if old_avatar_name == new_avatar_name:
            self.logger.info(f"Avatar for user {user_id} is already set to {new_avatar_name}. No action taken.")
            await self.user_repo.refresh(user)
            return user

        try:
            # 2. 【核心修改】开启一个自动管理的事务块
            async with self.user_repo.db.begin_nested():
                # 所有数据库相关的操作都放在这个代码块里
                new_file_record = await self.file_record_service.register_uploaded_file(
                    object_name=avatar_dto.object_name,
                    original_filename=avatar_dto.original_filename,
                    content_type=avatar_dto.content_type,
                    file_size=avatar_dto.file_size,
                    profile_name="user_avatars",
                    uploader_context=user_context,
                    etag=avatar_dto.etag,
                    commit=False
                )

                await self._cleanup_old_avatar_records(old_avatar_name)

                user.avatar_url = new_file_record.object_name
                self.user_repo.db.add(user)

                # 3. 【核心修改】不再需要手动 commit()
                # 当代码块无异常结束时，事务会自动提交

        except Exception as e:
            # 4. 【核心修改】不再需要手动 rollback()
            # 如果 async with 块内部发生异常，事务会自动回滚
            # 这里只剩下记录日志和重新抛出异常的职责
            self.logger.error(f"Failed to link new avatar for user {user_id}: {e}")
            raise e

        # 5. 阶段二的外部非事务性操作，完全不变
        if old_avatar_name:
            try:
                await self.file_service.delete_file(old_avatar_name, profile_name="user_avatars")
            except Exception as e:
                self.logger.error(f"数据库更新成功，但删除旧的物理头像文件 {old_avatar_name} 失败: {e}")

        await self.user_repo.refresh(user)
        return user

    async def restore_users(self, user_ids: List[UUID], current_user: UserContext) -> int:
        """
        从回收站中批量恢复用户。
        """
        # 在这里可以添加权限检查，例如只有超级管理员才能恢复
        # user_policy.can_restore(current_user)

        # 调用 BaseRepository 提供的通用恢复方法
        restored_count = await self.user_repo.restore_by_ids(user_ids)
        if restored_count > 0:
            self.logger.info(f"User {current_user.username} restored {restored_count} users.")
        return restored_count

    async def deactivate_and_anonymize_users(self, user_ids: List[UUID], current_user: UserContext) -> int:
        """
        永久停用并匿名化用户账户，替代物理删除。
        """
        # 权限检查：确保操作者是超级管理员，并且不能停用自己
        if not current_user.is_superuser:
            raise PermissionDeniedException("只有超级管理员才能执行此操作")
        if current_user.id in user_ids:
            raise UnauthorizedException("不能永久停用自己的账户")

        # 1. 开启一个事务
        async with self.user_repo.db.begin_nested():
            # 2. 从回收站中获取用户
            users_to_deactivate = await self.user_repo.get_by_ids(user_ids, view_mode=ViewMode.DELETED.value)
            if len(users_to_deactivate) != len(set(user_ids)):
                raise NotFoundException("一个或多个要操作的用户不存在于回收站中")

            # 3. 逐个匿名化用户信息
            count = 0
            for user in users_to_deactivate:
                if user.is_superuser:
                    raise PermissionDeniedException(f"不能永久停用超级管理员账户: {user.username}")

                # 抹去个人敏感信息
                user.username = f"deleted_user_{user.id.hex[:8]}"  # 使用部分hex确保唯一性
                user.email = f"{user.id}@deleted.local"
                user.full_name = "已注销用户"
                user.phone = None
                user.avatar_url = None  # 头像的物理文件可在后续清理
                user.hashed_password = get_password_hash(f"locked-{uuid.uuid4()}")  # 设置一个随机且无法登录的密码

                # 锁定账户并标记为非活跃
                user.is_active = False
                user.is_locked = True

                self.user_repo.db.add(user)
                count += 1

        # 4. 事务会自动提交
        self.logger.info(f"User {current_user.username} permanently deactivated {count} users.")

        # 注意：这里我们没有清理物理头像文件。
        # 这是一个可以接受的策略，因为文件记录已被软删除，
        # 后续可以通过一个定时清理任务来处理这些“孤儿”文件。
        return count
