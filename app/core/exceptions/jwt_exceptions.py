from app.core.exceptions import BaseBusinessException
from app.core.response_codes import ResponseCodeEnum


class UnauthorizedException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.AUTH_ERROR, message=message)

class TokenExpiredException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_EXPIRED.message)
        self.code = 401

class InvalidTokenException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_INVALID.message)
        self.code = 401

class TokenRevokedException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_REVOKED.message)
        self.code = 401

class TokenTypeMismatchException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_TYPE_MISMATCH.message)
        self.code = 401
