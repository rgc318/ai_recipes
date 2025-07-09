# app/repositories/user_repository.py

from typing import Optional, Union
from uuid import UUID

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.models.user import User
from app.schemas.user_schemas import UserCreate, UserUpdate

from app.crud.base_repo import BaseRepository  # 假设你已经写好的通用CRUD基类


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self):
        super().__init__(User)

    async def get_by_id(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        stmt = select(self.model).where(self.model.id == user_id, self.model.is_deleted == False)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        stmt = select(self.model).where(self.model.username == username, self.model.is_deleted == False)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: EmailStr) -> Optional[User]:
        stmt = select(self.model).where(self.model.email == email, self.model.is_deleted == False)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, user_data: Union[UserCreate, dict]) -> User:
        if isinstance(user_data, BaseModel):
            user_data = user_data.dict(exclude_unset=True)
        return await super().create(db, user_data)

    async def update(self, db: AsyncSession, user_id: UUID, updates: Union[UserUpdate, dict]) -> Optional[User]:
        if isinstance(updates, BaseModel):
            updates = updates.dict(exclude_unset=True)
        return await super().update(db, user_id, updates)

    async def soft_delete(self, db: AsyncSession, user_id: UUID) -> bool:
        user = await self.get_by_id(db, user_id)
        if not user:
            return False
        user.is_deleted = True
        db.add(user)
        await db.commit()
        return True
