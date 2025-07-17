from datetime import timedelta, datetime
from typing import Optional

from app.core.logger import get_logger
from app.config import settings
from app.core.security.hasher import get_hasher
from app.core.security.providers.auth_provider import AuthProvider
from app.core.exceptions import UserLockedOutException
from app.db.repository_factory_auto import RepositoryFactory
from app.schemas.user_schemas import CredentialsRequest, PrivateUser
from app.services.user_service import UserService
from app.enums.auth_method import AuthMethod

logger = get_logger("credentials_provider")


class CredentialsProvider(AuthProvider[CredentialsRequest]):
    def __init__(self, repo_factory: RepositoryFactory, data: CredentialsRequest):
        super().__init__(repo_factory=repo_factory, data=data)
        self._user: PrivateUser | None = None  # ✅ 实例变量
        self.user_service = UserService(repo_factory)

    async def authenticate(self) -> tuple[str, timedelta] | None:
        user = await self.get_user_by_identity(self.data.username)

        if not user:
            await self._verify_fake_password()
            return None
        self._user = user  # 缓存起来
        if self._is_locked(user):
            raise UserLockedOutException()

        if not self._verify_password(self.data.password, user.hashed_password):
            await self._handle_failed_login(user)
            return None

        await self._handle_successful_login(user)
        return self.get_access_token(user, remember_me=self.data.remember_me)

    async def get_user(self) -> Optional[PrivateUser]:
        return self._user
    # ==== 内部工具函数 ====

    def _validate_auth_method(self, user: PrivateUser) -> bool:
        return user.auth_method == AuthMethod.app

    def _is_locked(self, user: PrivateUser) -> bool:
        return (
            user.is_locked or
            user.login_attempts >= settings.security_settings.max_login_attempts
        )

    async def _handle_failed_login(self, user: PrivateUser):
        """【优化】委托给 UserService 处理"""
        await self.user_service.record_failed_login(user.id)

    async def _handle_successful_login(self, user: PrivateUser):
        """【优化】委托给 UserService 处理"""
        await self.user_service.record_successful_login(user.id)

    def _verify_password(self, plain: str, hashed: str) -> bool:
        return get_hasher().verify(plain, hashed)

    async def _verify_fake_password(self):
        fake_hash = settings.security_settings.fake_password_hash
        get_hasher().verify("fake-password", fake_hash)