import datetime
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import HTTPException, status

from app.db.repository_factory_auto import RepositoryFactory
from app.db.crud.user_repo import UserRepository
from app.models import User
from app.schemas.user_schemas import UserCreate, PrivateUser
from app.core.security.password_utils import get_password_hash, verify_password
from app.utils.jwt_utils import create_access_token
from app.services.user_service import UserService
from app.enums.auth_method import AuthMethod
from app.core.global_exception import UserLockedOut
from app.config import settings


class AuthService:
    def __init__(self, repo_factory: RepositoryFactory):
        self.factory = repo_factory
        self.user_repo: UserRepository = repo_factory.user

    async def register_user(self, user_in: UserCreate) -> User:
        if await self.user_repo.get_by_username(user_in.username):
            raise HTTPException(status_code=400, detail="Username already exists")

        if user_in.email and await self.user_repo.get_by_email(user_in.email):
            raise HTTPException(status_code=400, detail="Email already exists")

        hashed_password = get_password_hash(user_in.password)
        user_data = user_in.model_dump(exclude={"password"})
        user_data["hashed_password"] = hashed_password
        user_data["auth_method"] = AuthMethod.app  # 默认使用账号密码注册

        user_orm = await self.user_repo.create(user_data)
        return user_orm

    async def login_user(self, username: str, password: str, remember_me: bool = False) -> tuple[str, timedelta]:
        user = await self.user_repo.get_by_username(username)

        if not user:
            self.verify_fake_password()  # 防止用户枚举
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if user.login_attempts >= settings.security_settings.max_login_attempts or user.is_locked:
            raise UserLockedOut()

        if not verify_password(password, user.hashed_password):
            user.login_attempts += 1
            await self.user_repo.update(user.id, user)
            if user.login_attempts >= settings.security_settings.max_login_attempts:
                await UserService(self.factory).lock_user(user)
                user = await self.user_repo.get_by_id(user.id)  # 重新获取，更新锁定状态
                if user.is_locked:
                    raise UserLockedOut()
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # 成功登录
        user.login_attempts = 0
        user.last_login_at = datetime.utcnow()
        await self.user_repo.update(user.id, user)

        token, expires, _jti = create_access_token(
            data={"sub": str(user.id)}, remember_me=remember_me
        )
        return token, expires

    async def change_password(self, user_id: UUID, old_password: str, new_password: str) -> bool:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not verify_password(old_password, user.password):
            raise HTTPException(status_code=401, detail="Incorrect old password")

        hashed_password = get_password_hash(new_password)
        await self.user_repo.update(user.id, {"password": hashed_password})
        return True

    async def reset_password(self, email: str, new_password: str) -> bool:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="User is inactive")
        hashed_password = get_password_hash(new_password)
        await self.user_repo.update(user.id, {"password": hashed_password})
        return True

    def verify_fake_password(self):
        verify_password("fake-password", "$2b$12$JdHtJOlkPFwyxdjdygEzPOtYmdQF5/R5tHxw5Tq8pxjubyLqdIX5i")
