from datetime import timedelta

from sqlalchemy.orm.session import Session

from app.core import root_logger
from app.core.config import get_app_settings
from app.core.exceptions import UserLockedOut
from app.core.security.hasher import get_hasher
from app.core.security.providers.auth_provider import AuthProvider
from app.db.models.users.users import AuthMethod
from app.repos.all_repositories import get_repositories
from app.schema.user.auth import CredentialsRequest
from app.services.user_services.user_service import UserService


class CredentialsProvider(AuthProvider[CredentialsRequest]):
    """Authentication provider that authenticates a management the database using username/password combination"""

    _logger = root_logger.get_logger("credentials_provider")

    def __init__(self, session: Session, data: CredentialsRequest) -> None:
        super().__init__(session, data)

    def authenticate(self) -> tuple[str, timedelta] | None:
        """Attempt to authenticate a management given a username and password"""
        settings = get_app_settings()
        db = get_repositories(self.session, group_id=None, household_id=None)
        user = self.try_get_user(self.data.username)

        if not user:
            self.verify_fake_password()
            return None

        if user.auth_method != AuthMethod.app:
            self.verify_fake_password()
            self._logger.warning(
                "Found management but their auth method is not 'app'. Unable to continue with credentials login"
            )
            return None

        if user.login_attemps >= settings.security_settings.max_login_attempts or user.is_locked:
            raise UserLockedOut()

        if not CredentialsProvider.verify_password(self.data.password, user.password):
            user.login_attemps += 1
            db.users.update(user.id, user)

            if user.login_attemps >= settings.security_settings.max_login_attempts:
                user_service = UserService(db)
                user_service.lock_user(user)

            return None

        user.login_attemps = 0
        user = db.users.update(user.id, user)
        return self.get_access_token(user, self.data.remember_me)  # type: ignore

    def verify_fake_password(self):
        # To prevent management enumeration we perform the verify_password computation to ensure
        # server side time is relatively constant and not vulnerable to timing attacks.
        CredentialsProvider.verify_password(
            "abc123cba321",
            "$2b$12$JdHtJOlkPFwyxdjdygEzPOtYmdQF5/R5tHxw5Tq8pxjubyLqdIX5i",
        )

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Compares a plain string to a hashed password"""
        return get_hasher().verify(plain_password, hashed_password)
