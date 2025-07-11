from enum import Enum


class ResponseCodeEnum(Enum):

    CREATED = (201, "created")
    INTERNAL_ERROR = (500, "服务器内部错误")
    SUCCESS = (20000, "请求成功")
    VALIDATION_ERROR = (40001, "参数验证失败")
    AUTH_ERROR = (40100, "认证失败")
    FORBIDDEN = (40300, "没有权限")
    NOT_FOUND = (40400, "资源不存在")
    SERVER_ERROR = (50000, "服务器内部错误")

    USER_ALREADY_EXISTS = (40010, "用户已存在")
    USER_NOT_FOUND = (40010, "用户不存在")
    CHANGE_PASSWORD_FAILED = (40020, "修改密码失败")
    RESET_PASSWORD_FAILED = (40030, "重置密码失败")
    LOGIN_FAILED = (40040, "登录失败")
    USER_LOCKED_OUT = (40050, "用户已被锁定")

    def __init__(self, code: int, message: str):
        self._code = code
        self._message = message

    @property
    def code(self):
        return self._code

    @property
    def message(self):
        return self._message
