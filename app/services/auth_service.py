import datetime
from typing import Type, Any, Coroutine
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import HTTPException
from pydantic import BaseModel

from app.db.repository_factory_auto import RepositoryFactory
from app.db.crud.user_repo import UserRepository
from app.models import User
from app.schemas.user_schemas import UserCreate
from app.core.security.password_utils import get_password_hash, verify_password
from app.utils.jwt_utils import decode_token, revoke_token, create_refresh_token
from app.enums.auth_method import AuthMethod
from app.core.exceptions import UserLockedOutException, UserAlreadyExistsException
from app.core.security.providers import AuthProvider, CredentialsProvider
from app.utils.jwt_utils import (
    decode_token,
    validate_token_type,
    rotate_refresh_token,
    create_access_token,
)
# === 登录方式注册表（未来支持更多方式在此扩展）===
AUTH_PROVIDER_REGISTRY: dict[AuthMethod, Type[AuthProvider]] = {
    AuthMethod.app: CredentialsProvider,
    # AuthMethod.email_code: EmailCodeProvider,
    # AuthMethod.wechat: WeChatProvider,
    # AuthMethod.github: GitHubProvider,
}

class AuthService:
    def __init__(self, repo_factory: RepositoryFactory):
        self.factory = repo_factory
        self.user_repo: UserRepository = repo_factory.user

    async def register_user(self, user_in: UserCreate) -> User:
        if await self.user_repo.get_by_username(user_in.username):
            raise UserAlreadyExistsException()

        if user_in.email and await self.user_repo.get_by_email(user_in.email):
            raise HTTPException(status_code=400, detail="Email already exists")

        hashed_password = get_password_hash(user_in.password)
        user_data = user_in.model_dump(exclude={"password"})
        user_data["hashed_password"] = hashed_password
        user_data["auth_method"] = AuthMethod.app  # 默认使用账号密码注册

        user_orm = await self.user_repo.create(user_data)
        return user_orm

    async def login_user(self, method: AuthMethod, data: BaseModel) -> dict[str, str | timedelta | Any]:
        """
        登录入口：根据认证方式调用不同 Provider 执行认证。
        返回 access_token 和有效期。
        """
        provider_cls = AUTH_PROVIDER_REGISTRY.get(method)
        if not provider_cls:
            raise HTTPException(status_code=400, detail=f"Unsupported auth method: {method}")

        provider = provider_cls(repo_factory=self.factory, data=data)  # ✅ 传入 repo_factory
        access_token, access_expires = await provider.authenticate()
        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # 获取 user_id（由 provider 决定返回什么）
        user = await provider.get_user()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")


        user_id = str(user.id)
        token_data = {"sub": user_id}

        refresh_token, refresh_exp, _ = await create_refresh_token(token_data, user_id)

        # 5. 返回一个结构清晰的字典
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "access_expires_at": datetime.now() + access_expires,
            "refresh_expires_at": datetime.now() + refresh_exp,
        }

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
        await self.user_repo.update(user.id, {"hashed_password": hashed_password})
        return True

    async def logout_user(self, token: str) -> bool:
        """
        退出登录：撤销当前 token
        """
        try:
            payload = await decode_token(token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if not jti or not exp:
                raise HTTPException(status_code=400, detail="Invalid token payload")
            expires_in = int(exp - datetime.now().timestamp())
            await revoke_token(jti, expires_in=expires_in)
            return True
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Logout failed: {str(e)}")

    async def refresh_token(self, token: str) -> dict:
        """
        使用 refresh token 获取新的 access token 与 refresh token（轮换机制）
        """
        # 1. 解码 Refresh Token
        payload = await decode_token(token)

        # 2. 验证 token 类型
        validate_token_type(payload, "refresh")

        # 3. 拿到 user_id 和 old_jti
        user_id = payload["sub"]
        old_jti = payload["jti"]

        # 4. 构建通用数据（sub 等）
        token_data = {"sub": user_id}

        # 5. 撤销旧 RefreshToken + 生成新 RefreshToken
        new_refresh_token, refresh_exp, new_jti = await rotate_refresh_token(
            old_jti=old_jti,
            user_id=user_id,
            data=token_data,
        )

        # 6. 同时生成新的 AccessToken
        new_access_token, access_exp, _ = create_access_token(token_data)

        # 7. 返回结构
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "expires_at": datetime.now() + access_exp,
        }