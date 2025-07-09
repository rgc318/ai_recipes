from typing import TypeVar, Generic, Optional, Type, List, Union, Dict, Any
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from math import ceil
from sqlalchemy import asc, desc, or_, func
import logging

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

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

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
            if column is not None:
                conditions.append(column.ilike(f"%{search}%"))
        if conditions:
            stmt = stmt.where(or_(*conditions))
        return stmt

    async def get_by_id(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        stmt = self._base_stmt().where(self.model.id == id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        stmt = self._base_stmt().offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_with_filters(
        self,
        db: AsyncSession,
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

            # 计算总数时，复用相同筛选和搜索条件，改用COUNT(*)
            count_stmt = select(func.count()).select_from(self.model).where(self.model.is_deleted == False)
            count_stmt = self.apply_filters(count_stmt, filters)
            if search and search_fields:
                count_stmt = self.apply_search(count_stmt, search, search_fields)

            count_result = await db.execute(count_stmt)
            total = count_result.scalar() or 0

            stmt = self.apply_ordering(stmt, order_by)
            stmt = stmt.offset((page - 1) * per_page).limit(per_page)

            result = await db.execute(stmt)
            items = result.scalars().all()

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

    async def count(self, db: AsyncSession) -> int:
        stmt = self._base_stmt()
        result = await db.execute(stmt)
        return len(result.scalars().all())

    async def create(self, db: AsyncSession, obj_in: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        if isinstance(obj_in, BaseModel):
            # Pydantic v1 用 obj_in.dict(exclude_unset=True)
            # Pydantic v2 用 obj_in.model_dump(exclude_unset=True)
            obj_in = obj_in.dict(exclude_unset=True)
        db_obj = self.model(**obj_in)  # type: ignore
        db.add(db_obj)
        try:
            await db.commit()
            await db.refresh(db_obj)
        except Exception as e:
            await db.rollback()
            logger.error(f"Create failed: {e}")
            raise
        return db_obj

    async def create_many(self, db: AsyncSession, objs: List[CreateSchemaType]) -> List[ModelType]:
        db_objs = [self.model(**obj.dict(exclude_unset=True)) for obj in objs]
        db.add_all(db_objs)
        try:
            await db.commit()
            for obj in db_objs:
                await db.refresh(obj)
        except Exception as e:
            await db.rollback()
            logger.error(f"Batch create failed: {e}")
            raise
        return db_objs

    async def update(
        self, db: AsyncSession, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        if isinstance(obj_in, BaseModel):
            obj_in = obj_in.dict(exclude_unset=True)
        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        if hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.utcnow()

        db.add(db_obj)
        try:
            await db.commit()
            await db.refresh(db_obj)
        except Exception as e:
            await db.rollback()
            logger.error(f"Update failed: {e}")
            raise
        return db_obj

    async def delete(self, db: AsyncSession, id: UUID) -> bool:
        obj = await self.get_by_id(db, id)
        if not obj:
            return False
        await db.delete(obj)
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Delete failed: {e}")
            raise
        return True

    async def soft_delete(self, db: AsyncSession, id: UUID) -> bool:
        obj = await self.get_by_id(db, id)
        if not obj:
            return False
        obj.is_deleted = True
        if hasattr(obj, "deleted_at"):
            obj.deleted_at = datetime.utcnow()
        db.add(obj)
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Soft delete failed: {e}")
            raise
        return True
