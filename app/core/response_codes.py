from enum import Enum


class ResponseCodeEnum(Enum):

    # === 通用响应码 ===
    SUCCESS = (0, "请求成功")
    CREATED = (201, "资源创建成功")
    VALIDATION_ERROR = (40001, "参数验证失败")
    AUTH_ERROR = (40100, "认证失败")
    FORBIDDEN = (40300, "没有权限")
    NOT_FOUND = (40400, "资源不存在")
    SERVER_ERROR = (50000, "服务器内部错误")

    # === 用户相关 ===
    USER_ALREADY_EXISTS = (40010, "用户已存在")
    USER_NOT_FOUND = (40011, "用户不存在")
    USER_LOCKED_OUT = (40012, "用户已被锁定")
    USER_INACTIVE = (40013, "用户未激活")
    USER_UPDATE_FAILED = (40014, "用户更新失败")
    USER_DELETE_FAILED = (40015, "用户删除失败")

    # === 登录/注册 ===
    LOGIN_FAILED = (40101, "登录失败")
    REGISTER_FAILED = (40102, "注册失败")
    INVALID_CREDENTIALS = (40103, "用户名或密码错误")
    TOKEN_EXPIRED = (40104, "Token 已过期")
    TOKEN_INVALID = (40105, "无效 Token")
    TOKEN_REVOKED = (40106, "Token 已被吊销")
    TOKEN_TYPE_MISMATCH = (40107, "Token 类型不匹配")
    def __init__(self, code: int, message: str):
        self._code = code
        self._message = message

    @property
    def code(self):
        return self._code

    @property
    def message(self):
        return self._message
