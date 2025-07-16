from typing import TypeVar, Generic, Optional, Type, List, Union, Dict, Any
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from math import ceil
from sqlalchemy import asc, desc, or_, func
import logging
import time

from app.db.repo_registrar import RepositoryRegistrar
from app.metrics.repo_metrics import repository_sql_duration

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

logger = logging.getLogger(__name__)

class PageResponse(BaseModel, Generic[ModelType]):
    items: List[ModelType]
    total: int
    page: int
    total_pages: int
    per_page: int

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], RepositoryRegistrar):
    def __init__(self, db: AsyncSession, model: Type[ModelType], context: dict = None):
        self.db = db
        self.model = model
        self.context = context or {}

    def _base_stmt(self):
        return select(self.model).where(self.model.is_deleted == False)

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

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        stmt = self._base_stmt().where(self.model.id == id)
        return await self._run_and_scalar(stmt, "get_by_id")

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
            stmt = self._base_stmt()
            stmt = self.apply_filters(stmt, filters)

            if search and search_fields:
                stmt = self.apply_search(stmt, search, search_fields)

            count_stmt = select(func.count()).select_from(self.model).where(self.model.is_deleted == False)
            count_stmt = self.apply_filters(count_stmt, filters)
            if search and search_fields:
                count_stmt = self.apply_search(count_stmt, search, search_fields)

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            stmt = self.apply_ordering(stmt, order_by)
            stmt = stmt.offset((page - 1) * per_page).limit(per_page)

            items = await self._run_and_scalars(stmt, "list_with_filters")

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

    async def create(self, obj_in: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        return await self._measure("create", self._create_internal(obj_in))

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

    async def create_many(self, objs: List[CreateSchemaType]) -> List[ModelType]:
        db_objs = [self.model(**obj.dict(exclude_unset=True)) for obj in objs]
        self.db.add_all(db_objs)
        try:
            await self.db.commit()
            for obj in db_objs:
                await self.db.refresh(obj)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Batch create failed: {e}")
            raise
        return db_objs

    async def update(self, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
        data = obj_in.dict(exclude_unset=True) if isinstance(obj_in, BaseModel) else obj_in
        for field, value in data.items():
            setattr(db_obj, field, value)

        if hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.utcnow()

        self.db.add(db_obj)
        try:
            await self.db.commit()
            await self.db.refresh(db_obj)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Update failed: {e}")
            raise
        return db_obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.get_by_id(id)
        if not obj:
            return False
        await self.db.delete(obj)
        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Delete failed: {e}")
            raise
        return True

    async def soft_delete(self, id: UUID) -> bool:
        obj = await self.get_by_id(id)
        if not obj:
            return False
        obj.is_deleted = True
        if hasattr(obj, "deleted_at"):
            obj.deleted_at = datetime.utcnow()
        if hasattr(obj, "updated_at"):
            obj.updated_at = datetime.utcnow()
        self.db.add(obj)
        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Soft delete failed: {e}")
            raise
        return True

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
    async def _measure(self, method_name: str, coro):
        start = time.perf_counter()
        try:
            return await coro
        finally:
            elapsed = time.perf_counter() - start
            repository_sql_duration.labels(
                repository=self.__class__.__name__,
                method=method_name
            ).observe(elapsed)
