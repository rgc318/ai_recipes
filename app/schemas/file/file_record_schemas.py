from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, computed_field

from app.core.logger import logger
from app.infra.storage.storage_factory import storage_factory
from app.utils.url_builder import build_public_storage_url


class FileRecordRead(BaseModel):
    """
    用于从 API 返回文件记录信息的模型 (增强版)。
    """
    id: UUID
    object_name: str = Field(..., description="文件在对象存储中的唯一路径/键")
    original_filename: str = Field(..., description="文件的原始名称")
    description: Optional[str] = None
    alt_text: Optional[str] = None
    file_size: int = Field(..., description="文件大小（字节）")
    content_type: str = Field(..., description="文件的 MIME 类型")
    uploader_id: UUID = Field(..., description="上传该文件的用户ID")
    created_at: datetime

    # 【新增】将 profile_name 暴露给 API
    profile_name: str = Field(..., description="上传时使用的 Storage Profile 名称")
    is_associated: Optional[bool] = False
    is_deleted: Optional[bool] = False
    # 【新增】将 etag 暴露给 API (可选)
    etag: Optional[str] = Field(None, description="文件在对象存储中的 ETag")

    # url: Optional[str] = Field(None, description="文件的完整可访问 URL")

    # 我们可以额外添加一个由 Service 层动态生成的 url 字段
    # @computed_field
    # @property
    # def url(self) -> Optional[str]:
    #     """
    #     动态生成此文件记录的完整可访问URL。
    #     """
    #     # 假设所有通过这个 Schema 返回的都是公开文件
    #     # 如果需要区分公开/私有，可以在这里加入更多逻辑
    #     if self.object_name:
    #         return build_public_storage_url(self.object_name)
    #     return None

    @computed_field
    @property
    def url(self) -> Optional[str]:
        """
        动态生成此文件记录的完整可访问URL。
        """
        if not self.object_name or not self.profile_name:
            return None
        try:
            # 1. 它不再需要 Depends()
            # 2. 它直接使用导入的全局 factory
            client = storage_factory.get_client_by_profile(self.profile_name)
            return client.build_final_url(self.object_name)
        except Exception as e:
            logger.error(f"Failed to build URL for {self.object_name}: {e}")
            return None  # 失败时安全返回 null

    # 允许从 ORM 对象模型进行转换
    model_config = {
        "from_attributes": True
    }


class FileRecordUpdate(BaseModel):
    """
    用于更新文件元数据的模型 (例如，重命名)。
    """
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    # ... 其他字段
    description: Optional[str] = None
    alt_text: Optional[str] = None
    # --- 你需要在这里添加下面这一行 ---
    object_name: Optional[str] = None
    is_associated: Optional[bool] = None

# 【新增】用于创建文件记录的 Schema
class FileRecordCreate(BaseModel):
    object_name: str
    original_filename: str
    file_size: int
    content_type: str
    uploader_id: UUID
    profile_name: str
    description: Optional[str] = None
    alt_text: Optional[str] = None
    etag: Optional[str] = None
    # is_associated: Optional[str] = False

class FileFilterParams(BaseModel):
    """
    文件记录列表的过滤参数模型。
    FastAPI 会自动将查询参数映射到这个模型的字段上。
    """
    original_filename: Optional[str] = Field(None, description="按原始文件名进行模糊搜索")
    content_type: Optional[str] = Field(None, description="按文件MIME类型精确过滤")
    profile_name: Optional[str] = Field(None, description="按上传时使用的Profile名称过滤")
    uploader_id: Optional[UUID] = Field(None, description="按上传用户ID过滤")


class StorageUsageStats(BaseModel):
    group_key: Optional[str] = None
    total_files: int
    total_size_bytes: int


class MoveFilePayload(BaseModel):
    profile_name: str = Field(..., description="文件所在的 Profile 名称。")
    record_id: UUID = Field(..., description="要移动的文件的数据库记录ID。")
    destination_key: str = Field(..., description="文件在对象存储中的新路径/键。")

class FileInfo(BaseModel):
    object_name: str
    size: int
    last_modified: datetime

class BulkActionPayload(BaseModel):
    record_ids: List[UUID] = Field(..., min_length=1)

class FileDeleteCheckResponse(BaseModel):
    """
    用于文件删除预检的API响应模型。
    """
    status: str  # 'success', 'warning', or 'error'
    message: str
    needs_confirmation: bool = False
    in_use_files: Optional[List[str]] = None
    safe_to_delete_count: int = 0
    in_use_count: int = 0
