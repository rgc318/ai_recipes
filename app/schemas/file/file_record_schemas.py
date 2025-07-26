from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class FileRecordRead(BaseModel):
    """
    用于从 API 返回文件记录信息的模型 (增强版)。
    """
    id: UUID
    object_name: str = Field(..., description="文件在对象存储中的唯一路径/键")
    original_filename: str = Field(..., description="文件的原始名称")
    file_size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件的 MIME 类型")
    uploader_id: UUID = Field(..., description="上传该文件的用户ID")
    created_at: datetime

    # 【新增】将 profile_name 暴露给 API
    profile_name: str = Field(..., description="上传时使用的 Storage Profile 名称")

    # 【新增】将 etag 暴露给 API (可选)
    etag: Optional[str] = Field(None, description="文件在对象存储中的 ETag")

    # 我们可以额外添加一个由 Service 层动态生成的 url 字段
    url: Optional[str] = Field(None, description="文件的可访问 URL")

    # 允许从 ORM 对象模型进行转换
    model_config = {
        "from_attributes": True
    }


class FileRecordUpdate(BaseModel):
    """
    用于更新文件元数据的模型 (例如，重命名)。
    """
    original_filename: Optional[str] = None

# 【新增】用于创建文件记录的 Schema
class FileRecordCreate(BaseModel):
    object_name: str
    original_filename: str
    file_size: int
    content_type: str
    uploader_id: UUID
    profile_name: str
    etag: Optional[str] = None

class FileFilterParams(BaseModel):
    """
    文件记录列表的过滤参数模型。
    FastAPI 会自动将查询参数映射到这个模型的字段上。
    """
    original_filename: Optional[str] = Field(None, description="按原始文件名进行模糊搜索")
    content_type: Optional[str] = Field(None, description="按文件MIME类型精确过滤")
    profile_name: Optional[str] = Field(None, description="按上传时使用的Profile名称过滤")
    uploader_id: Optional[UUID] = Field(None, description="按上传用户ID过滤")