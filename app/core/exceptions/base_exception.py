# app/core/exceptions.py

from typing import Optional

from app.core.response_codes import ResponseCodeEnum


class BaseBusinessException(Exception):
    def __init__(
            self,
            code_enum: Optional[ResponseCodeEnum] = None,
            code: Optional[int] = None,
            status_code: int = 200,
            message: Optional[str] = None,
            extra: Optional[dict] = None,
    ):
        self.code = code if code is not None else code_enum.code
        self.message = message or code_enum.message
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.code}] {self.message}"

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "extra": self.extra,
        }


class NotFoundException(BaseBusinessException):
    """
    当请求的资源在数据库中不存在时抛出。
    """
    def __init__(self, message: str = "资源不存在"):
        # 我们使用刚刚在 ResponseCodeEnum 中定义的 NOT_FOUND
        super().__init__(ResponseCodeEnum.NOT_FOUND, message=message)


class AlreadyExistsException(BaseBusinessException):
    """
    当尝试创建一个已存在的资源时抛出（例如，用户名或角色名重复）。
    """
    def __init__(self, message: str = "资源已存在"):
        super().__init__(ResponseCodeEnum.ALREADY_EXISTS, message=message)
class PermissionDeniedException(BaseBusinessException):
    """
    权限不足
    """
    def __init__(self, message: str = "权限不足"):
        super().__init__(ResponseCodeEnum.FORBIDDEN, message=message)

class FileException(BaseBusinessException):
    """
    当请求的资源在数据库中不存在时抛出。
    """
    def __init__(self, message: str = "资源不存在"):
        # 我们使用刚刚在 ResponseCodeEnum 中定义的 NOT_FOUND
        super().__init__(ResponseCodeEnum.FILE_EXCEPTION, message=message)
class ConcurrencyConflictException(BaseBusinessException):
    def __init__(self, message: str = "操作失败，数据已被他人修改，请刷新后重试"):
        super().__init__(ResponseCodeEnum.ALREADY_EXISTS, message=message)
