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
from app.services._base_service import BaseService
from app.services.user_service import UserService
from app.utils.jwt_utils import decode_token, revoke_token, create_refresh_token
from app.enums.auth_method import AuthMethod
from app.core.exceptions import UserLockedOutException, UserAlreadyExistsException, AlreadyExistsException, \
    UnauthorizedException, NotFoundException, InvalidTokenException, TokenExpiredException, TokenRevokedException
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

class AuthService(BaseService):
    def __init__(self, repo_factory: RepositoryFactory):
        super().__init__()  # 【修改3】调用父类的构造函数，注入 settings 和 logger
        self.user_service: UserService = UserService(repo_factory)
        self.factory = repo_factory
        self.user_repo: UserRepository = repo_factory.user

    async def register_user(self, user_in: UserCreate) -> User:
        if await self.user_repo.get_by_username(user_in.username):
            raise UserAlreadyExistsException()

        if user_in.email and await self.user_repo.get_by_email(user_in.email):
            raise AlreadyExistsException("邮箱已被注册")

        hashed_password = get_password_hash(user_in.password)
        user_data = user_in.model_dump(exclude={"password"})
        user_data["hashed_password"] = hashed_password
        user_data["auth_method"] = AuthMethod.app  # 默认使用账号密码注册

        try:
            # 3. 调用不带commit的repo.create方法
            user_orm = await self.user_repo.create(user_data)
            # 4. 在Service层决定提交事务
            await self.user_repo.commit()
            return user_orm
        except Exception as e:
            await self.user_repo.rollback()
            raise e

    async def login_user(self, method: AuthMethod, data: BaseModel) -> dict[str, str | timedelta | Any]:
        """
        登录入口：根据认证方式调用不同 Provider 执行认证。
        返回 access_token 和有效期。
        """
        provider_cls = AUTH_PROVIDER_REGISTRY.get(method)
        if not provider_cls:
            raise UnauthorizedException(f"不支持的认证方式: {method}")

        provider = provider_cls(repo_factory=self.factory, data=data)  # ✅ 传入 repo_factory
        access_token, access_expires = await provider.authenticate()
        if not access_token:
            raise UnauthorizedException("用户名或密码错误")

        # 获取 user_id（由 provider 决定返回什么）
        user = await provider.get_user()

        if not user:
            raise UnauthorizedException("认证成功后无法获取用户信息")


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
            raise NotFoundException("用户不存在")

        if not verify_password(old_password, user.password):
            raise UnauthorizedException("旧密码不正确")

        await self.user_service.change_password(user_id, new_password)
        return True

    async def reset_password(self, email: str, new_password: str) -> bool:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise NotFoundException("用户不存在")
        if not user.is_active:
            raise UnauthorizedException("用户账户已被禁用")

        await self.user_service.reset_password_by_email(email, new_password)
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
                raise InvalidTokenException("无效的令牌载荷")
            expires_in = int(exp - datetime.now().timestamp())
            await revoke_token(jti, expires_in=expires_in)
            return True
        except (InvalidTokenException, TokenExpiredException, TokenRevokedException) as e:
            # 如果令牌本身就无效或已过期，登出操作也视为“成功”
            self.logger.warning(f"尝试登出一个无效或已过期的令牌: {e}")
            return True
        except Exception as e:
            self.logger.error(f"登出时发生未知错误: {e}", exc_info=True)
            raise

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
            "token_type": "bearer",
            "access_expires_at": datetime.now() + access_exp,
            "refresh_expires_at": datetime.now() + refresh_exp,
        }