# === 认证/登录相关异常 ===
from app.core.exceptions.base_exception import BaseBusinessException
from app.enums.response_codes import ResponseCodeEnum


class LoginFailedException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.LOGIN_FAILED, message=message)

class RegisterFailedException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.REGISTER_FAILED, message=message)

class InvalidCredentialsException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.INVALID_CREDENTIALS, message=message)