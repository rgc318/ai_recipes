from app.core.exceptions.base_exception import BaseBusinessException
from app.core.response_codes import ResponseCodeEnum

# === 用户相关异常 ===
class UserAlreadyExistsException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.USER_ALREADY_EXISTS, message=message)

class UserNotFoundException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.USER_NOT_FOUND, message=message)

class UserLockedOutException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.USER_LOCKED_OUT, message=message)

class UserInactiveException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.USER_INACTIVE, message=message)

class UserUpdateFailedException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.USER_UPDATE_FAILED, message=message)

class UserDeleteFailedException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.USER_DELETE_FAILED, message=message)

