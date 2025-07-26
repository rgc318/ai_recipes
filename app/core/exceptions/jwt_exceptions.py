from app.core.exceptions import BaseBusinessException
from app.enums.response_codes import ResponseCodeEnum


class UnauthorizedException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.AUTH_ERROR, message=message)

class TokenExpiredException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_EXPIRED.message)
        self.code = ResponseCodeEnum.TOKEN_EXPIRED.code

class InvalidTokenException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_INVALID.message)
        self.code = ResponseCodeEnum.TOKEN_INVALID.code

class TokenRevokedException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_REVOKED.message)
        self.code = ResponseCodeEnum.TOKEN_REVOKED.code

class TokenTypeMismatchException(UnauthorizedException):
    def __init__(self, message: str = None):
        super().__init__(message or ResponseCodeEnum.TOKEN_TYPE_MISMATCH.message)
        self.code = ResponseCodeEnum.TOKEN_TYPE_MISMATCH.code
