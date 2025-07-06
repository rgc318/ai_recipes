from typing import Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User
from app.schemas.user_schemas import UserCreate, UserUpdate
from pydantic import BaseModel as PydanticBaseModel


class UserCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id, User.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username, User.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email, User.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_data: Union[UserCreate, dict]) -> User:
        if isinstance(user_data, PydanticBaseModel):
            user_data = user_data.model_dump()
        user = User(**user_data)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user_id: UUID, updates: Union[UserUpdate, dict]) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None

        if isinstance(updates, PydanticBaseModel):
            updates = updates.model_dump(exclude_unset=True)

        for key, value in updates.items():
            setattr(user, key, value)

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def soft_delete(self, user_id: UUID) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.is_deleted = True
        self.session.add(user)
        await self.session.commit()
        return True
