from typing import Any, Optional, Dict, TypeVar, Generic, List, Union

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeMeta
import logging

from app.core.response_codes import ResponseCodeEnum

logger = logging.getLogger(__name__)

T = TypeVar('T')


# === Generic Pydantic Response Schema ===
class StandardResponse(BaseModel, Generic[T]):
    code: int
    message: str
    data: Optional[T]

    class Config:
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "code": 0,
                "message": "Success",
                "data": {}
            }
        }


# === 自动序列化工具 ===
def to_json_compatible(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.dict()

    if isinstance(data, list):
        return [to_json_compatible(item) for item in data]

    if isinstance(data.__class__, DeclarativeMeta):
        # ORM 实例 -> dict（需用户实现 __pydantic_model__）
        model = getattr(data.__class__, "__pydantic_model__", None)
        if model:
            return model.from_orm(data).dict()
        else:
            return str(data)  # 或 raise 更明确

    if isinstance(data, dict):
        return {k: to_json_compatible(v) for k, v in data.items()}

    return data  # int, str, bool, None, etc.


# === 成功响应 ===
def response_success(
    data: Any = None,
    code: ResponseCodeEnum = ResponseCodeEnum.SUCCESS,
    http_status: int = 200,
    message: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
    final_message = message or code.message
    logger.debug(f"Response Success | code: {code.code}, message: {final_message}")

    try:
        # 🟡 先自定义序列化（处理 ORM, Pydantic）
        serialized_data = to_json_compatible(data)

        # ✅ 再使用 FastAPI 内置方法进行最终兼容处理（处理 datetime, UUID 等）
        encoded_data = jsonable_encoder(serialized_data)

    except Exception as e:
        logger.exception("Error serializing response data")
        encoded_data = str(data)

    return JSONResponse(
        status_code=http_status,
        content={
            "code": code.code,
            "message": final_message,
            "data": encoded_data
        },
        headers=headers
    )


# === 错误响应 ===
def response_error(
    code: ResponseCodeEnum,
    http_status: int = 400,
    message: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> JSONResponse:
    final_message = message or code.message
    logger.warning(f"Response Error | http_status: {http_status}, code: {code.code}, message: {final_message}")

    return JSONResponse(
        status_code=http_status,
        content={
            "code": code.code,
            "message": final_message,
            "data": None
        },
        headers=headers
    )
