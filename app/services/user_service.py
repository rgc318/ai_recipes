from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.crud.user_repo import UserRepository
from app.db.session import get_session
from app.models.user import User
from app.schemas.user_schemas import UserCreate, UserUpdate
from app.core.security.password_utils import get_password_hash  # 假设你实现了这个工具函数


class UserService:
    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session
        self.user_repo = UserRepository(session)

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def get_by_username(self, username: str) -> User:
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def get_by_email(self, email: str) -> User:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def create_user(self, user_in: UserCreate) -> User:
        # 检查用户名是否存在
        if await self.user_repo.get_by_username(user_in.username):
            raise HTTPException(status_code=400, detail="Username already exists")

        # 检查邮箱是否存在
        if user_in.email and await self.user_repo.get_by_email(user_in.email):
            raise HTTPException(status_code=400, detail="Email already exists")

        # 加密密码
        hashed_password = get_password_hash(user_in.password)
        user_data = user_in.dict(exclude={"password"})
        user_data["hashed_password"] = hashed_password

        return await self.user_repo.create(user_data)

    async def update_user(self, user_id: UUID, updates: UserUpdate) -> User:
        existing_user = await self.user_repo.get_by_id(user_id)
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")

        # 检查邮箱是否冲突
        if updates.email and updates.email != existing_user.email:
            existing_email_user = await self.user_repo.get_by_email(updates.email)
            if existing_email_user:
                raise HTTPException(status_code=400, detail="Email already exists")

        return await self.user_repo.update(user_id, updates)

    async def delete_user(self, user_id: UUID) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return await self.user_repo.soft_delete(user_id)
