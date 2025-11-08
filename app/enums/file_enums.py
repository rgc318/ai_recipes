# app/schemas/file/file_schemas.py (或新文件)
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
# ...

class UploadMode(str, Enum):
    """
    定义预签名上传的模式。
    继承 (str, Enum) 允许 Pydantic 自动将 YAML/JSON 中的字符串
    (如 "put_url") 校验并转换为这个枚举成员。
    """
    PUT_URL = "put_url"
    POST_POLICY = "post_policy"
    MULTIPART = "multipart" # 你在 capabilities 中也定义了这个，一起放进来
