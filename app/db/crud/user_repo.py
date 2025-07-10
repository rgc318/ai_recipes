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

    # 如果没有自定义逻辑，可直接使用父类 soft_delete 方法
