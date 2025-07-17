from typing import TypeVar, Generic, Optional, Type, List, Union, Dict, Any
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, timezone
from math import ceil
from sqlalchemy import asc, desc, or_, func, update
import logging
import time

from app.core.types.common import ModelType
from app.db.repo_registrar import RepositoryRegistrar
from app.metrics.repo_metrics import repository_sql_duration
from app.schemas.page_schemas import PageResponse


CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

logger = logging.getLogger(__name__)



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

    # ==========================
    # 数据查询方法 (Query) - 这部分基本无需改动
    # ==========================

    def _base_stmt(self):
        return select(self.model).where(self.model.is_deleted == False)

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

    def apply_ordering(self, stmt, order_by: str = ""):
        if not order_by:
            return stmt

        for clause in order_by.split(","):
            field, *direction = clause.strip().split(":")
            order_field = getattr(self.model, field, None)
            if not order_field:
                logger.warning(f"Ignored invalid order_by field: {field}")
                continue
            if direction and direction[0].lower() == "asc":
                stmt = stmt.order_by(asc(order_field))
            else:
                stmt = stmt.order_by(desc(order_field))
        return stmt

    def apply_filters(self, stmt, filters: Dict[str, Any]):
        for key, value in filters.items():
            column = getattr(self.model, key, None)
            if column is not None and value is not None:
                stmt = stmt.where(column == value)
        return stmt

    def apply_search(self, stmt, search: str, fields: List[str]):
        conditions = []
        for field in fields:
            column = getattr(self.model, field, None)
            try:
                if column is not None and hasattr(column, "ilike"):
                    conditions.append(column.ilike(f"%{search}%"))
            except Exception:
                logger.warning(f"Skipping search field {field}: not suitable for ilike")
        if conditions:
            stmt = stmt.where(or_(*conditions))
        return stmt

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



    async def list(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = self._base_stmt().offset(skip).limit(limit)
        return await self._run_and_scalars(stmt, "list")

    async def list_with_filters(
        self,
        filters: Dict[str, Any],
        order_by: str = "",
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> PageResponse[ModelType]:
        try:
            query  = self._base_stmt()
            query  = self.apply_filters(query , filters)

            if search and search_fields:
                query  = self.apply_search(query , search, search_fields)

            # 2. 基于上面的查询，构建一个高效的count子查询
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar_one() or 0

            # 3. 对主查询应用排序和分页
            query = self.apply_ordering(query, order_by)
            query = query.offset((page - 1) * per_page).limit(per_page)

            items = await self._run_and_scalars(query, "list_with_filters")

            return PageResponse(
                items=items,
                total=total,
                page=page,
                total_pages=ceil(total / per_page) if per_page else 0,
                per_page=per_page,
            )
        except Exception as e:
            logger.error(f"Error in list_with_filters: {e}")
            raise

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
