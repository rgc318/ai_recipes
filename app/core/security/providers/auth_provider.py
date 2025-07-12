import abc
from datetime import timedelta
from typing import TypeVar, Generic, Optional

from app.utils.jwt_utils import create_access_token
from app.config.settings import settings
from app.schemas.user_schemas import PrivateUser
from app.db.get_repo_factory import RepositoryFactory
from app.enums.auth_method import AuthMethod

T = TypeVar("T")  # 泛型参数：用于接受各种认证请求数据，如密码、验证码等


class AuthProvider(Generic[T], metaclass=abc.ABCMeta):
    """
    抽象认证提供器基类，用于定义统一认证接口与通用工具函数。
    子类如 CredentialsProvider、EmailCodeProvider 应继承此类。
    """

    def __init__(self, repo_factory: RepositoryFactory, data: T) -> None:
        self.db = repo_factory
        self.data = data
        self._cached_user: Optional[PrivateUser] = None

    def get_access_token(
        self,
        user: PrivateUser,
        remember_me: bool = False,
    ) -> tuple[str, timedelta]:
        """
        使用 jwt_utils 创建 access token，支持 remember_me 长效模式。
        可根据 settings 设置 token 签发算法和发行人。
        """
        payload = {"sub": str(user.id)}

        token, expires, _jti = create_access_token(
            data=payload,
            remember_me=remember_me,
        )

        return token, expires

    async def get_user_by_identity(self, identity: str) -> Optional[PrivateUser]:
        """
        获取用户（支持缓存）。尝试按用户名查找，不存在则按邮箱查找。
        """
        if self._cached_user:
            return self._cached_user

        user = await self.db.user.get_one(identity, "username", any_case=True)
        if not user:
            user = await self.db.user.get_one(identity, "email", any_case=True)

        self._cached_user = user
        return user

    @abc.abstractmethod
    async def authenticate(self) -> Optional[tuple[str, timedelta]]:
        """
        子类必须实现的认证方法。返回 (token, expires) 或 None 表示认证失败。
        """
        raise NotImplementedError("Subclasses must implement this method.")
