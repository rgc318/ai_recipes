from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlmodel import Field, Relationship

from app.models.base.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.users.user import User


class FileRecord(BaseModel, table=True):
    """
    文件记录实体类 (企业级增强版)。
    在数据库中存储上传到对象存储的文件的元数据。
    """
    __tablename__ = "file_record"

    # --- 核心元数据 ---
    object_name: str = Field(
        ...,
        unique=True,
        index=True,
        description="文件在对象存储中的唯一路径/键"
    )
    original_filename: str = Field(..., description="文件的原始名称")
    file_size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件的 MIME 类型")
    is_associated: Optional[bool] = Field(default=False, description="文件是否关联了业务数据")

    # 【新增】文件的 ETag，用于完整性校验
    etag: Optional[str] = Field(None, index=True, description="文件在对象存储中的 ETag")

    # --- 业务与关联 ---
    uploader_id: UUID = Field(foreign_key="user.id", index=True, description="上传该文件的用户ID")


    # 【新增】记录文件上传时使用的业务场景 Profile
    profile_name: str = Field(
        ...,
        index=True,
        description="上传时使用的 Storage Profile 名称"
    )

    uploader: "User" = Relationship(back_populates="uploaded_files")