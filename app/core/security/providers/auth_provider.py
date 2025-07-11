import abc
from datetime import UTC, datetime, timedelta
from typing import TypeVar, Generic, Optional

import jwt

from app.config.settings import settings
from app.schemas.user_schemas import PrivateUser
from app.db.get_repo_factory import RepositoryFactory  # ✅ 你自己的 repo factory 模块
from app.enums.auth_method import AuthMethod

T = TypeVar("T")  # 泛型参数

ALGORITHM = "HS256"
ISS = "app"
REMEMBER_ME_DURATION = timedelta(days=14)


class AuthProvider(Generic[T], metaclass=abc.ABCMeta):
    """Base Authentication Provider interface"""

    def __init__(self, repo_factory: RepositoryFactory, data: T) -> None:
        self.db = repo_factory  # ✅ 明确是 repo，不是原始 session
        self.data = data
        self.user: Optional[PrivateUser] = None
        self.__has_tried_user = False

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return hasattr(subclass, "authenticate") and callable(subclass.authenticate)

    def get_access_token(self, user: PrivateUser, remember_me=False) -> tuple[str, timedelta]:
        duration = timedelta(hours=settings.TOKEN_TIME)
        if remember_me and REMEMBER_ME_DURATION > duration:
            duration = REMEMBER_ME_DURATION
        return self.create_access_token({"sub": str(user.id)}, duration)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, timedelta]:
        to_encode = data.copy()
        expires_delta = expires_delta or timedelta(hours=settings.TOKEN_TIME)
        expire = datetime.now(UTC) + expires_delta

        to_encode.update({
            "exp": expire,
            "iss": ISS,
        })

        token = jwt.encode(to_encode, settings.SECRET, algorithm=ALGORITHM)
        return token, expires_delta

    async def try_get_user(self, username: str) -> Optional[PrivateUser]:
        """尝试获取用户，优先按用户名匹配，再按邮箱匹配"""
        if self.__has_tried_user:
            return self.user

        user = await self.db.users.get_one(username, "username", any_case=True)
        if not user:
            user = await self.db.users.get_one(username, "email", any_case=True)

        self.user = user
        self.__has_tried_user = True
        return user

    @abc.abstractmethod
    async def authenticate(self) -> Optional[tuple[str, timedelta]]:
        """Attempt to authenticate a user"""
        raise NotImplementedError
