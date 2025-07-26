import operator
from typing import TypeVar, Generic, Optional, Type, List, Union, Dict, Any

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, timezone
from math import ceil
from sqlalchemy import asc, desc, or_, func, update
import logging

from app.core.types.common import ModelType
from app.infra.db.repo_registrar import RepositoryRegistrar
from app.schemas.common.page_schemas import PageResponse


CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

logger = logging.getLogger(__name__)

OPERATOR_MAP = {
    'eq': operator.eq,          # 等于: field__eq=value
    'ne': operator.ne,          # 不等于
    'lt': operator.lt,          # 小于
    'le': operator.le,          # 小于等于
    'gt': operator.gt,          # 大于
    'ge': operator.ge,          # 大于等于
    'in': 'in_',                # 包含于: field__in=[v1, v2]
    'not_in': 'not_in',         # 不包含于
    'like': 'like',             # 模糊查询 (区分大小写)
    'ilike': 'ilike',           # 模糊查询 (不区分大小写): field__ilike=%value%
    'is_null': lambda c, v: c.is_(None) if v else c.isnot(None), # 是否为NULL
}

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], RepositoryRegistrar):
    def __init__(self, db: AsyncSession, model: Type[ModelType], context: dict = None):
        self.db = db
        self.model = model
        self.context = context or {}



    # ==========================
    # 事务控制方法 (Transaction Control)
    # ==========================

    async def commit(self):
        """提交当前数据库会话中的所有更改。"""
        await self.db.commit()

    async def rollback(self):
        """回滚当前数据库会话中的所有更改。"""
        await self.db.rollback()

    async def refresh(self, obj: ModelType):
        """用数据库中的最新状态刷新一个ORM对象。"""
        await self.db.refresh(obj)

    async def flush(self):
        """将当前会话中的变更刷入数据库，但不提交事务。"""
        await self.db.flush()

    # ==========================
    # 数据创建方法 (Create)
    # ==========================

    async def create(self, obj_in: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        """
        创建一个新的对象实例，并将其添加到会话中。
        """
        create_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        db_obj = self.model(**create_data)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def create_many(self, objs_in: List[CreateSchemaType]) -> List[ModelType]:
        """
        批量创建多个对象。
        """
        db_objs = [self.model(**obj.model_dump(exclude_unset=True)) for obj in objs_in]
        self.db.add_all(db_objs)
        await self.db.flush()
        for obj in db_objs:
            await self.db.refresh(obj)
        return db_objs

    # ==========================
    # 数据更新方法 (Update)
    # ==========================

    async def update(self, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
        """
        在内存中更新一个ORM对象的属性 (Read-Modify-Write模式)。
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # 自动更新 updated_at 字段 (如果存在)
        if hasattr(db_obj, "updated_at"):
            setattr(db_obj, "updated_at", datetime.now(timezone.utc))

        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def update_by_id(self, item_id: Any, update_data: Dict[str, Any]) -> int:
        """
        根据ID和数据字典直接更新数据库记录 (Direct Update模式)。
        """
        if not update_data:
            return 0

        # 自动更新 updated_at 字段 (如果存在)
        if hasattr(self.model, "updated_at"):
            update_data["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(self.model)
            .where(self.model.id == item_id)
            .values(**update_data)
        )
        result = await self.db.execute(stmt)
        return result.rowcount

    async def update_by_id_and_return(self, item_id: Any, update_data: Dict[str, Any]) -> Optional[ModelType]:
        """
        根据ID更新记录，并返回更新后的对象。
        注意：这依赖于数据库对 RETURNING 子句的支持 (如 PostgreSQL)。
        """
        if not update_data:
            return None

        if hasattr(self.model, "updated_at"):
            update_data["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(self.model)
            .where(self.model.id == item_id)
            .values(**update_data)
            .returning(self.model)  # <-- 关键部分
        )
        result = await self.db.execute(stmt)
        await self.commit()  # 直接更新需要手动提交
        return result.scalar_one_or_none()
    # ==========================
    # 数据删除方法 (Delete)
    # ==========================

    async def delete(self, db_obj: ModelType) -> None:
        """
        从数据库中物理删除一个对象。
        """
        await self.db.delete(db_obj)
        await self.db.flush()

    async def soft_delete(self, db_obj: ModelType) -> ModelType:
        """
        软删除一个对象 (设置 is_deleted = True)。
        """
        if hasattr(db_obj, "updated_at"):
            setattr(db_obj, "updated_at", datetime.now(timezone.utc))
        if hasattr(db_obj, "is_deleted"):
            setattr(db_obj, "is_deleted", True)
        if hasattr(db_obj, "deleted_at"):
            setattr(db_obj, "deleted_at", datetime.now(timezone.utc))

        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def soft_delete_by_ids(self, ids: List[UUID]) -> int:
        """
        根据ID列表，高效地批量软删除对象。

        Returns:
            受影响的行数 (即成功删除的记录数量)。
        """
        if not ids:
            return 0

        update_values = {
            "is_deleted": True,
            "deleted_at": datetime.now(timezone.utc)
        }
        # 自动更新 updated_at 字段 (如果存在)
        if hasattr(self.model, "updated_at"):
            update_values["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(self.model)
            .where(self.model.id.in_(ids))
            .values(**update_values)
        )
        result = await self.db.execute(stmt)
        # result.rowcount 返回受此 UPDATE 语句影响的行数
        return result.rowcount
    # ==========================
    # 数据查询方法 (Query) - 这部分基本无需改动
    # ==========================

    def _base_stmt(self):
        """
        构建基础查询语句，默认过滤掉软删除的记录 (如果模型支持)。
        """
        stmt = select(self.model)
        if hasattr(self.model, 'is_deleted'):
            # 使用 getattr 安全地获取列对象
            stmt = stmt.where(getattr(self.model, 'is_deleted') == False)
        return stmt

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        stmt = self._base_stmt().where(self.model.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


    async def get_by_ids(self, ids: List[UUID]) -> List[ModelType]:
        """
        根据一个ID列表，批量获取对象。
        这是一个非常高效的查询，可以避免在循环中进行多次数据库调用。

        Args:
            ids: 一个包含UUID的列表。

        Returns:
            找到的对象列表。
        """
        if not ids:
            return []

        stmt = self._base_stmt().where(self.model.id.in_(ids))
        return await self._run_and_scalars(stmt, "get_by_ids")

    def apply_ordering(self, stmt, order_by: List[str]):
        # 优化排序，使其接收列表，并去掉冒号约定
        if not order_by:
            return stmt.order_by(desc(self.model.created_at))  # 默认排序

        for sort_field in order_by:
            order_func = asc
            if sort_field.startswith('-'):
                sort_field = sort_field[1:]
                order_func = desc

            column = getattr(self.model, sort_field, None)
            if column:
                stmt = stmt.order_by(order_func(column))
        return stmt

    # def apply_filters(self, stmt, filters: Dict[str, Any]):
    #     for key, value in filters.items():
    #         column = getattr(self.model, key, None)
    #         if column is not None and value is not None:
    #             stmt = stmt.where(column == value)
    #     return stmt
    #
    # def apply_search(self, stmt, search: str, fields: List[str]):
    #     conditions = []
    #     for field in fields:
    #         column = getattr(self.model, field, None)
    #         try:
    #             if column is not None and hasattr(column, "ilike"):
    #                 conditions.append(column.ilike(f"%{search}%"))
    #         except Exception:
    #             logger.warning(f"Skipping search field {field}: not suitable for ilike")
    #     if conditions:
    #         stmt = stmt.where(or_(*conditions))
    #     return stmt

    async def get_one(self, value: str, field: str, any_case: bool = False):
        col = getattr(self.model, field)
        if any_case:
            stmt = select(self.model).where(
                col.ilike(value),
                self.model.is_deleted == False
            )
        else:
            stmt = select(self.model).where(
                col == value,
                self.model.is_deleted == False
            )
        return await self._run_and_scalar(stmt, f"get_one_by_{field}")

    async def find_by_field(self, value: Any, field_name: str, case_insensitive: bool = False) -> Optional[ModelType]:
        """通过指定字段查找单个对象 (可选)"""
        column = getattr(self.model, field_name)
        stmt = self._base_stmt()  # 应该也应用软删除过滤

        if case_insensitive:
            stmt = stmt.where(column.ilike(value))
        else:
            stmt = stmt.where(column == value)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = self._base_stmt().offset(skip).limit(limit)
        return await self._run_and_scalars(stmt, "list")

    # async def list_with_filters(
    #     self,
    #     filters: Dict[str, Any],
    #     order_by: str = "",
    #     search: Optional[str] = None,
    #     search_fields: Optional[List[str]] = None,
    #     page: int = 1,
    #     per_page: int = 10,
    # ) -> PageResponse[ModelType]:
    #     try:
    #         query  = self._base_stmt()
    #         query  = self.apply_filters(query , filters)
    #
    #         if search and search_fields:
    #             query  = self.apply_search(query , search, search_fields)
    #
    #         # 2. 基于上面的查询，构建一个高效的count子查询
    #         count_query = select(func.count()).select_from(query.subquery())
    #         total_result = await self.repo.execute(count_query)
    #         total = total_result.scalar_one() or 0
    #
    #         # 3. 对主查询应用排序和分页
    #         query = self.apply_ordering(query, order_by)
    #         query = query.offset((page - 1) * per_page).limit(per_page)
    #
    #         items = await self._run_and_scalars(query, "list_with_filters")
    #
    #         return PageResponse(
    #             items=items,
    #             total=total,
    #             page=page,
    #             total_pages=ceil(total / per_page) if per_page else 0,
    #             per_page=per_page,
    #         )
    #     except Exception as e:
    #         logger.error(f"Error in list_with_filters: {e}")
    #         raise

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model).where(self.model.is_deleted == False)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _create_internal(self, obj_in: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        data = obj_in.dict(exclude_unset=True) if isinstance(obj_in, BaseModel) else obj_in
        db_obj = self.model(**data)  # type: ignore
        self.db.add(db_obj)
        try:
            await self.db.commit()
            await self.db.refresh(db_obj)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[create] Failed: {e}")
            raise
        return db_obj


    async def _run_and_scalar(self, stmt, method: str):
        try:
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"[{method}] Failed: {e}")
            raise

    async def _run_and_scalars(self, stmt, method: str):
        try:
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"[{method}] Failed: {e}")
            raise

    # def _apply_dynamic_filters(self, stmt, filters: Dict[str, Any]):
    #     """
    #     一个强大的动态过滤器应用函数，理解 `field__operator` 语法。
    #     """
    #     if not filters:
    #         return stmt
    #
    #     for key, value in filters.items():
    #         if value is None or value == '':
    #             continue
    #
    #         parts = key.split('__')
    #         field_name = parts[0]
    #         op_name = parts[1] if len(parts) > 1 else 'eq'  # 默认为等于
    #
    #         # 特殊处理：关联查询
    #         # 这个逻辑可以根据需要扩展
    #         if field_name == 'role_ids' and op_name == 'in':
    #             from app.models.user import UserRole
    #             stmt = stmt.join(UserRole, self.model.id == UserRole.user_id).where(
    #                 UserRole.role_id.in_(value)).distinct()
    #             continue
    #
    #         # 普通字段查询
    #         column = getattr(self.model, field_name, None)
    #         if column is None:
    #             logger.warning(f"Ignored invalid filter field: {field_name}")
    #             continue
    #
    #         op_func = OPERATOR_MAP.get(op_name)
    #         if op_func:
    #             if isinstance(op_func, str):  # 'in_', 'not_in', 'like', 'ilike'
    #                 stmt = stmt.where(getattr(column, op_func)(value))
    #             else:  # 其他操作符
    #                 stmt = stmt.where(op_func(column, value))
    #         else:
    #             logger.warning(f"Ignored invalid filter operator: {op_name}")
    #     return stmt

    # =================================================================
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 替换此方法 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # =================================================================
    async def get_paged_list(
            self,
            *,
            page: int = 1,
            per_page: int = 10,
            filters: Optional[Dict[str, Any]] = None,
            sort_by: Optional[List[str]] = None,
            eager_loads: Optional[List[Any]] = None,
            stmt_in: Optional[Any] = None  # 1. 【关键修复】在这里添加 stmt_in 参数
    ) -> PageResponse[ModelType]:
        """
        【全新】通用的、支持动态过滤和排序的分页查询方法。
        这将是所有 Repo 的分页查询入口。
        """
        # 2. 【关键修复】如果传入了预处理过的 statement，就使用它；否则，创建默认的
        stmt = stmt_in if stmt_in is not None else self._base_stmt()

        # 3. 应用动态过滤
        stmt = self._apply_dynamic_filters(stmt, filters or {})

        # 4. 计算总数 (在分页前)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one_or_none() or 0

        if total == 0:
            return PageResponse(items=[], total=0, page=page, per_page=per_page, total_pages=0)

        # 5. 应用排序和分页
        stmt = self.apply_ordering(stmt, sort_by or [])
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        # 6. 应用预加载 (Eager Loading)
        if eager_loads:
            for option in eager_loads:
                stmt = stmt.options(option)

        # 7. 执行查询并返回结果
        items_result = await self.db.execute(stmt)
        items = items_result.unique().scalars().all()

        return PageResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=ceil(total / per_page) if per_page > 0 else 0,
        )
    # =================================================================

    # =================================================================
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 替换为下面两个方法 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # =================================================================

    def _build_condition(self, key: str, value: Any):
        """
        【新增】一个内部辅助函数，根据 key 和 value 构建单个查询条件。
        """
        parts = key.split('__')
        field_name = parts[0]
        op_name = parts[1] if len(parts) > 1 else 'eq'

        column = getattr(self.model, field_name, None)
        if column is None:
            logger.warning(f"Ignored invalid filter field: {field_name}")
            return None

        op_func = OPERATOR_MAP.get(op_name)
        if op_func:
            if isinstance(op_func, str):  # 'in_', 'not_in', 'like', 'ilike'
                # ✨ 关键增强：对 like 和 ilike 操作自动添加通配符
                if op_name in ('like', 'ilike'):
                    return getattr(column, op_func)(f"%{value}%")
                else:
                    return getattr(column, op_func)(value)
            else:  # 其他操作符
                return op_func(column, value)
        else:
            logger.warning(f"Ignored invalid filter operator: {op_name}")
            return None

    def _apply_dynamic_filters(self, stmt, filters: Dict[str, Any]):
        """
        【重构后】一个更强大、更简洁、职责更清晰的动态过滤器。
        """
        if not filters:
            return stmt

        or_conditions_data = filters.pop('__or__', {})
        and_conditions_data = filters

        # 处理 AND 条件
        for key, value in and_conditions_data.items():
            if value is None or value == '':
                continue
            condition = self._build_condition(key, value)
            if condition is not None:
                stmt = stmt.where(condition)

        # 处理 OR 条件
        if or_conditions_data:
            or_clauses = []
            for key, value in or_conditions_data.items():
                if value is None or value == '':
                    continue
                condition = self._build_condition(key, value)
                if condition is not None:
                    or_clauses.append(condition)

            if or_clauses:
                stmt = stmt.where(or_(*or_clauses))

        return stmt
    # =================================================================