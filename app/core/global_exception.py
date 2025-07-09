# app/core/exceptions.py

class BaseBusinessException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

class UserNotFoundException(BaseBusinessException):
    def __init__(self):
        super().__init__(code=40404, message="用户不存在")

class UserLockedOut(BaseBusinessException):
    def __init__(self):
        super().__init__(code=40404, message="用户不存在")