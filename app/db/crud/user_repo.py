from datetime import datetime
from typing import Optional, Union
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.models.user import User
from app.schemas.user_schemas import UserCreate, UserUpdate
from app.db.crud.base_repo import BaseRepository

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        super().__init__(db, User, context)

    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(self.model).where(
            self.model.username == username,
            self.model.is_deleted == False
        )
        return await self._run_and_scalar(stmt, "get_by_username")

    async def get_by_email(self, email: EmailStr) -> Optional[User]:
        stmt = select(self.model).where(
            self.model.email == email,
            self.model.is_deleted == False
        )
        return await self._run_and_scalar(stmt, "get_by_email")

    # 如果确实有特殊字段处理需求，可以保留 create 重写，否则可以删除此方法，使用父类的
    async def create(self, user_data: Union[UserCreate, dict]) -> User:
        return await super().create(user_data)

    async def update(self, user_id: UUID, updates: Union[UserUpdate, dict]) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        return await super().update(user, updates)

    async def get_by_phone(self, phone: str) -> Optional[User]:
        stmt = select(self.model).where(
            self.model.phone == phone,
            self.model.is_deleted == False
        )
        return await self._run_and_scalar(stmt, "get_by_phone")

    async def set_last_login(self, user_id: UUID) -> None:
        user = await self.get_by_id(user_id)
        if not user:
            return
        user.last_login = datetime.utcnow()
        self.db.add(user)
        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise e

    async def change_password(self, user_id: UUID, hashed_password: str) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.hashed_password = hashed_password
        self.db.add(user)
        try:
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            raise e

    async def disable_user(self, user_id: UUID) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = False
        self.db.add(user)
        try:
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            raise e

    async def enable_user(self, user_id: UUID) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = True
        self.db.add(user)
        try:
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            raise e