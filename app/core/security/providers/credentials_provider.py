from datetime import timedelta, datetime
from app.core.logger import get_logger
from app.config import settings
from app.core.security.hasher import get_hasher
from app.core.security.providers.auth_provider import AuthProvider
from app.core.global_exception import UserLockedOut
from app.db.repository_factory_auto import RepositoryFactory
from app.schemas.user_schemas import CredentialsRequest, PrivateUser
from app.services.user_service import UserService
from app.db.get_repo_factory import get_repository_factory
from app.enums.auth_method import AuthMethod

logger = get_logger("credentials_provider")


class CredentialsProvider(AuthProvider[CredentialsRequest]):
    def __init__(self, repo_factory: RepositoryFactory, data: CredentialsRequest):
        super().__init__(repo_factory=repo_factory, data=data)

    async def authenticate(self) -> tuple[str, timedelta] | None:
        user = await self.get_user_by_identity(self.data.username)

        if not user:
            await self._verify_fake_password()
            return None

        if self._is_locked(user):
            raise UserLockedOut()

        if not self._verify_password(self.data.password, user.hashed_password):
            await self._handle_failed_login(user)
            return None

        await self._handle_successful_login(user)
        return self.get_access_token(user, remember_me=self.data.remember_me)

    # ==== 内部工具函数 ====

    def _validate_auth_method(self, user: PrivateUser) -> bool:
        return user.auth_method == AuthMethod.app

    def _is_locked(self, user: PrivateUser) -> bool:
        return (
            user.is_locked or
            user.login_attempts >= settings.security_settings.max_login_attempts
        )

    async def _handle_failed_login(self, user: PrivateUser):
        user.login_attempts += 1
        await self.db.user.update(user.id, user)

        if user.login_attempts >= settings.security_settings.max_login_attempts:
            await UserService(self.db).lock_user(user)
            logger.warning(f"User {user.username} locked due to failed attempts")

    async def _handle_successful_login(self, user: PrivateUser):
        user.login_attempts = 0
        user.last_login_at = datetime.utcnow()
        await self.db.user.update(user.id, user)

    def _verify_password(self, plain: str, hashed: str) -> bool:
        return get_hasher().verify(plain, hashed)

    async def _verify_fake_password(self):
        fake_hash = settings.security_settings.fake_password_hash
        get_hasher().verify("fake-password", fake_hash)