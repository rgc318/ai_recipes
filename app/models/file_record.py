from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship

# 假设 BaseModel 继承自 SQLModel 且包含 id, created_at 等公共字段
from app.models.base.base_model import BaseModel

# 使用 TYPE_CHECKING 来避免循环导入
# 这是一种标准的 Python 类型提示技巧
if TYPE_CHECKING:
    from app.models.user import User

class FileRecord(BaseModel, table=True):
    """
    文件记录实体类。
    用于在数据库中存储上传到对象存储（如 MinIO）的文件的元数据。
    """
    __tablename__ = "file_record"

    # --- 核心元数据 ---
    object_name: str = Field(
        ...,
        unique=True,
        index=True,
        description="文件在对象存储中的唯一路径/键 (e.g., avatars/user_id/uuid.png)"
    )
    original_filename: str = Field(..., description="文件的原始名称，用于显示")
    file_size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件的 MIME 类型 (e.g., image/png)")

    # --- 关联关系 ---
    uploader_id: UUID = Field(foreign_key="user.id", index=True, description="上传该文件的用户ID")

    # 定义了从 FileRecord 到 User 的关系
    uploader: "User" = Relationship(back_populates="uploaded_files")