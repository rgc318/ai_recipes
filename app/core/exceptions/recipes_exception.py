from app.core.exceptions import BaseBusinessException
from app.enums.response_codes import ResponseCodeEnum


class BusinessRuleException(BaseBusinessException):
    def __init__(self, message: str = None):
        super().__init__(ResponseCodeEnum.USER_ALREADY_EXISTS, message=message)