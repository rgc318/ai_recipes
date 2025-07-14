# app/core/exceptions.py

from typing import Optional

from app.core.response_codes import ResponseCodeEnum


class BaseBusinessException(Exception):
    def __init__(
            self,
            code_enum: ResponseCodeEnum,
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
