from datetime import timedelta
from app.core.logger import get_logger
from app.config import settings
from app.core.security.hasher import get_hasher
from app.core.security.providers.auth_provider import AuthProvider
from app.core.global_exception import UserLockedOut
from app.schemas.user_schemas import CredentialsRequest
from app.services.user_service import UserService
from app.db.get_repo_factory import get_repository_factory
from app.enums.auth_method import AuthMethod

logger = get_logger("credentials_provider")


class CredentialsProvider(AuthProvider[CredentialsRequest]):
    def __init__(self, data: CredentialsRequest):
        # ✅ 正确调用基类初始化
        repo_factory = None  # 占位，异步初始化
        super().__init__(repo_factory=repo_factory, data= data)

    async def authenticate(self) -> tuple[str, timedelta] | None:
        # ✅ 获取仓库（可放入 __init__）
        repo_factory = await get_repository_factory()
        self.db = repo_factory  # ✅ 设置基类中的 self.db

        user = await self.db.users.get_by_username(self.data.username)

        if not user:
            await self.verify_fake_password()
            return None

        if user.auth_method != AuthMethod.app:
            await self.verify_fake_password()
            logger.warning("Auth method mismatch for user.")
            return None

        if user.login_attempts >= settings.security_settings.max_login_attempts or user.is_locked:
            raise UserLockedOut()

        if not self.verify_password(self.data.password, user.password):
            user.login_attempts += 1
            await self.db.users.update(user.id, user)
            if user.login_attempts >= settings.security_settings.max_login_attempts:
                await UserService(self.db).lock_user(user)
            return None

        user.login_attempts = 0
        await self.db.users.update(user.id, user)

        # ✅ 直接使用父类中的 get_access_token 方法（无需重复调用 jwt_utils）
        return self.get_access_token(user, self.data.remember_me)

    async def verify_fake_password(self):
        self.verify_password("fake-password", "$2b$12$JdHtJOlkPFwyxdjdygEzPOtYmdQF5/R5tHxw5Tq8pxjubyLqdIX5i")

    def verify_password(self, plain: str, hashed: str) -> bool:
        return get_hasher().verify(plain, hashed)
