from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# 这是一个 DTO (Data Transfer Object)，用于 API 的输出
# 它精确地反映了数据库模型 FileRecord 的结构
class FileRecordRead(BaseModel):
    """
    用于从 API 返回文件记录信息的模型。
    """
    id: UUID
    object_name: str = Field(..., description="文件在对象存储中的唯一路径/键")
    original_filename: str = Field(..., description="文件的原始名称")
    file_size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件的 MIME 类型")
    uploader_id: UUID = Field(..., description="上传该文件的用户ID")
    created_at: datetime

    # 我们可以额外添加一个由 Service 层动态生成的 url 字段
    url: Optional[str] = Field(None, description="文件的可访问 URL (通常是预签名 URL)")

    # 允许从 ORM 对象模型进行转换
    class Config:
        from_attributes = True


# 未来可能需要的 Schema
class FileRecordUpdate(BaseModel):
    """
    用于更新文件元数据的模型 (例如，重命名)。
    """
    original_filename: Optional[str] = None