from datetime import datetime, timezone
from math import ceil
from typing import Optional, Union, Any, List
from uuid import UUID
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import selectinload

from app.models.user import User, Role, UserRole
from app.schemas.user_schemas import UserCreate, UserUpdate, UserReadWithRoles
from app.schemas.page_schemas import PageResponse
from app.db.crud.base_repo import BaseRepository

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        super().__init__(db, User, context)

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户。"""
        # 使用继承的 _base_stmt 来确保 is_deleted == False 条件
        stmt = self._base_stmt().where(self.model.username == username)
        # 建议使用 _run_and_scalar，因为它已经包含了日志和异常处理
        return await self._run_and_scalar(stmt, "get_by_username")

    async def get_by_email(self, email: EmailStr) -> Optional[User]:
        """根据邮箱获取用户。"""
        stmt = self._base_stmt().where(self.model.email == email)
        return await self._run_and_scalar(stmt, "get_by_email")


    async def get_by_phone(self, phone: str) -> Optional[User]:
        """根据电话号码获取用户。"""
        stmt = self._base_stmt().where(self.model.phone == phone)
        return await self._run_and_scalar(stmt, "get_by_phone")

    async def get_by_id_with_roles_permissions(self, user_id: UUID) -> Optional[User]:
        """根据ID获取用户，并预加载其角色和权限。"""
        stmt = (
            self._base_stmt()
            .where(self.model.id == user_id)
            .options(selectinload(self.model.roles).selectinload(Role.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


    # --- 【新增】高级分页和过滤方法 ---
    # async def get_paged_users(
    #         self,
    #         page: int = 1,
    #         per_page: int = 10,
    #         order_by: str = "created_at:desc",
    #         username: Optional[str] = None,
    #         email: Optional[str] = None,
    #         phone: Optional[str] = None,
    #         role_ids: Optional[List[UUID]] = None,
    #         is_active: Optional[bool] = None,
    # ) -> PageResponse[UserReadWithRoles]:
    #     """
    #     一个功能强大的用户列表查询方法（修复版），支持：
    #     - 分页 (Pagination)
    #     - 排序 (Ordering)
    #     - 模糊搜索 (Search on username, email, full_name)
    #     - 按角色ID过滤 (Filtering by roles)
    #     - 按激活状态过滤 (Filtering by active status)
    #     - 高效加载用户的角色信息 (Eager loading roles)
    #     """
    #     # --- 构建通用的过滤和JOIN逻辑 ---
    #     # 1. 基础查询语句
    #     query = select(self.model)
    #
    #     # 2. 应用过滤条件
    #     query = query.where(self.model.is_deleted == False)
    #
    #     # 针对每个独立字段，如果传入了值，就添加一个 WHERE 条件
    #     if username:
    #         query = query.where(self.model.username.ilike(f"%{username}%"))
    #
    #     if email:
    #         query = query.where(self.model.email.ilike(f"%{email}%"))
    #
    #     if phone:
    #         query = query.where(self.model.phone.ilike(f"%{phone}%"))
    #
    #     if is_active is not None:
    #         query = query.where(self.model.is_active == is_active)
    #
    #     # 按角色ID过滤 (关键的多表查询逻辑)
    #     if role_ids:
    #         # 使用 distinct() 确保在 join 后每个用户只被考虑一次
    #         query = query.join(UserRole, self.model.id == UserRole.user_id).where(
    #             UserRole.role_id.in_(role_ids)).distinct()
    #
    #     # --- 执行计数查询 (第一步) ---
    #     # 在应用了所有过滤和JOIN之后，但在应用分页和排序之前，进行计数
    #     # 使用 subquery 来确保 count 的正确性
    #     count_query = select(func.count()).select_from(query.subquery())
    #     total_result = await self.db.execute(count_query)
    #     total = total_result.scalar_one()
    #
    #     if total == 0:
    #         return PageResponse(items=[], total=0, page=page, per_page=per_page, total_pages=0)
    #
    #     # --- 获取分页后的用户ID (第二步) ---
    #     # 选择主键ID，应用排序和分页
    #     paginated_ids_query = query.with_only_columns(self.model.id)
    #     paginated_ids_query = self.apply_ordering(paginated_ids_query, order_by)
    #     paginated_ids_query = paginated_ids_query.offset((page - 1) * per_page).limit(per_page)
    #
    #     paginated_ids_result = await self.db.execute(paginated_ids_query)
    #     user_ids_for_page = paginated_ids_result.scalars().all()
    #
    #     if not user_ids_for_page:
    #         return PageResponse(items=[], total=total, page=page, per_page=per_page,
    #                             total_pages=ceil(total / per_page) if per_page > 0 else 0)
    #
    #     # --- 获取完整的用户数据 (第三步) ---
    #     # 使用上面获取的ID列表来查询完整的用户对象，并预加载角色
    #     # 保持原始排序是很重要的
    #     final_query = (
    #         select(self.model)
    #         .where(self.model.id.in_(user_ids_for_page))
    #         .options(
    #             # 使用链式 selectinload 预加载 roles，以及 roles 内部的 permissions
    #             selectinload(self.model.roles).selectinload(Role.permissions)
    #         )
    #     )
    #     # 重新应用排序，以保证最终结果的顺序与分页ID的顺序一致
    #     final_query = self.apply_ordering(final_query, order_by)
    #
    #     items_result = await self.db.execute(final_query)
    #     # 使用 .unique() 来确保即使JOIN导致了重复行，也只返回唯一的ORM对象
    #     items = items_result.unique().scalars().all()
    #
    #     return PageResponse[UserReadWithRoles](
    #         items=items,
    #         total=total,
    #         page=page,
    #         total_pages=ceil(total / per_page) if per_page > 0 else 0,
    #         per_page=per_page,
    #     )

    async def revoke_role_from_user(self, user: User, role: Role) -> User:
        """在内存中为用户移除一个角色。不提交。"""
        if role in user.roles:
            user.roles.remove(role)
            self.db.add(user)
            await self.db.flush()
        return user

    async def set_user_roles(self, user: User, roles: List[Role]) -> User:
        """
        在内存中更新用户的角色列表，但不提交事务。
        这是写操作，由Service层负责调用和最终的commit。
        """
        user.roles = roles
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def assign_role_to_user(self, user: User, role: Role) -> User:
        """在内存中为用户添加一个角色。不提交。"""
        if role not in user.roles:
            user.roles.append(role)
            self.db.add(user)
            await self.db.flush()
        return user

    async def get_paged_users(
            self,
            *,
            page: int,
            per_page: int,
            filters: dict,
            sort_by: List[str],
    ) -> PageResponse[User]:
        """
        获取用户分页列表。
        此方法现在只是对 BaseRepository.get_paged_list 的一个简单封装，
        主要目的是指定需要预加载的关联字段。
        """
        eager_loading_options = [
            selectinload(self.model.roles).selectinload(Role.permissions)
        ]
        return await self.get_paged_list(
            page=page,
            per_page=per_page,
            filters=filters,
            sort_by=sort_by,
            # 指定需要预加载的关系，支持链式加载
            eager_loads=eager_loading_options
        )

    # 如果确实有特殊字段处理需求，可以保留 create 重写，否则可以删除此方法，使用父类的
    # async def create(self, user_data: Union[UserCreate, dict]) -> User:
    #     return await super().create(user_data)
    #
    # async def update(self, user_id: UUID, updates: Union[UserUpdate, dict]) -> Optional[User]:
    #     user = await self.get_by_id(user_id)
    #     if not user:
    #         return None
    #     return await super().update(user, updates)