from typing import Any, Optional, Dict, TypeVar, Generic, List, Union

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeMeta
import logging

from app.enums.response_codes import ResponseCodeEnum

logger = logging.getLogger(__name__)

T = TypeVar('T')

# 【新增】步骤一：创建一个可重用的、内部的 Cookie 处理函数
def _apply_cookie_modifications(
    response: JSONResponse,
    set_cookies: Optional[List[Dict[str, Any]]] = None,
    delete_cookies: Optional[List[str]] = None,
):
    """
    一个内部辅助函数，用于在给定的 Response 对象上应用 cookie 的设置和删除操作。
    """
    # 设置新的 cookies
    if set_cookies:
        for cookie_params in set_cookies:
            params = cookie_params.copy()
            cookie_key = params.pop('key', None)
            if cookie_key is not None:
                response.set_cookie(key=cookie_key, **params)

    # 删除指定的 cookies
    if delete_cookies:
        for cookie_key in delete_cookies:
            response.delete_cookie(key=cookie_key)

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
        return data.model_dump()

    if isinstance(data, list):
        return [to_json_compatible(item) for item in data]

    if isinstance(data.__class__, DeclarativeMeta):
        # ORM 实例 -> dict（需用户实现 __pydantic_model__）
        model = getattr(data.__class__, "__pydantic_model__", None)
        if model:
            return model.from_orm(data).model_dump()
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
    headers: Optional[Dict[str, str]] = None,
    set_cookies: Optional[List[Dict[str, Any]]] = None, # 参数名改为更明确的 set_cookies
    delete_cookies: Optional[List[str]] = None,      # 新增 delete_cookies 参数
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

    # 1. 先创建 JSONResponse 对象
    response = JSONResponse(
        status_code=http_status,
        content={
            "code": code.code,
            "message": final_message,
            "data": encoded_data
        },
        headers=headers
    )
    # 【修改】步骤二：统一调用内部辅助函数
    _apply_cookie_modifications(response, set_cookies, delete_cookies)
    # 3. 返回被修改过的 response 对象
    return response

# === 错误响应 ===
def response_error(
    code: Union[ResponseCodeEnum, int] = ResponseCodeEnum.SERVER_ERROR,
    http_status: int = 200,
    message: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    set_cookies: Optional[List[Dict[str, Any]]] = None, # 新增 set_cookies 参数
    delete_cookies: Optional[List[str]] = None,
) -> JSONResponse:

    if isinstance(code, ResponseCodeEnum):
        code_val = code.code
        msg_val = message if message is not None else code.message
    else:  # 如果传入的是整数
        code_val = code
        msg_val = message if message is not None else "操作失败"

    logger.warning(f"Response Error | http_status: {http_status}, code: {code_val}, message: {msg_val}")

    response = JSONResponse(
        status_code=http_status,
        content={
            "code": code_val,
            "message": msg_val,
            "data": None
        },
        headers=headers
    )

    # 【修改】步骤二：统一调用内部辅助函数
    _apply_cookie_modifications(response, set_cookies, delete_cookies)

    return response
