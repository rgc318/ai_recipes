# app/core/exceptions.py

from typing import Optional

from app.core.response_codes import ResponseCodeEnum


class BaseBusinessException(Exception):
    code: int = 50000
    message: str = "业务异常"
    status_code: int = 400

    def __init__(self, code: Optional[int] = None, message: Optional[str] = None):
        if code:
            self.code = code
        if message:
            self.message = message
        super().__init__(self.message)

class UserNotFoundException(BaseBusinessException):
    code = 40404
    message = "用户不存在"
    status_code = 404

class UserAlreadyExistsException(BaseBusinessException):
    code = ResponseCodeEnum.USER_ALREADY_EXISTS
    message = "用户已存在"
    status_code = 200

class UserLockedOut(BaseBusinessException):
    code = 40301
    message = "用户已被锁定，请稍后再试"
    status_code = 403

class UnauthorizedException(BaseBusinessException):
    code = "UNAUTHORIZED"
    message = "未授权"
    status_code = 401