from uuid import UUID

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class FileUploadResponse(BaseModel):
    object_name: str = Field(..., description="文件在存储桶中的完整路径/键。")
    url: str = Field(..., description="上传后文件的最终可访问 URL。")
    final_filename: Optional[str] = Field(None, description="为文件生成的唯一文件名。")

class FileExistsResponse(BaseModel):
    exists: bool

class FileListResponse(BaseModel):
    files: List[str]

class PresignedGetUrlResponse(BaseModel):
    url: str = Field(..., description="生成的用于下载的预签名 URL。")

class PresignedPutUrlResponse(BaseModel):
    upload_url: str = Field(..., description="生成的用于上传的预签名 URL。")
    object_name: str = Field(..., description="上传时必须使用的唯一对象名称。")
    url: str = Field(..., description="成功上传后，对象的最终访问 URL。")

class UploadResult(BaseModel):
    """
    用于从 FileService 返回上传结果的统一数据传输对象 (DTO)。
    """
    record_id: Optional[UUID] = Field(..., description="新创建的 FileRecord 在数据库中的ID")
    object_name: str = Field(..., description="文件在对象存储中的唯一路径/键")
    url: str = Field(..., description="文件的可公开访问 URL")
    etag: Optional[str] = Field(None, description="文件的 ETag，由对象存储生成")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    content_type: Optional[str] = Field(None, description="文件的 MIME 类型")

class PresignedUploadURL(BaseModel):
    """
    用于返回预签名上传 URL 的 DTO。
    """
    upload_url: str = Field(..., description="客户端可用于直接上传的预签名 URL")
    object_name: str = Field(..., description="文件上传后在对象存储中的唯一路径/键")
    url: str = Field(..., description="文件上传成功后的最终可访问 URL")


class AvatarLinkDTO(BaseModel):
    """
    用于关联已上传头像的数据传输对象。
    """
    object_name: str = Field(..., description="由后端生成并返回的唯一对象名称。")
    original_filename: str = Field(..., description="用户上传的原始文件名。")
    content_type: str = Field(..., description="文件的MIME类型。")
    file_size: int = Field(..., description="文件的字节大小。")

    # ETag 并非所有对象存储都保证返回，设为可选更安全
    etag: Optional[str] = Field(None, description="文件上传后，由对象存储返回的ETag。")



class PresignedAvatarRequest(BaseModel):
    original_filename: str

# 【新增】为安全的POST策略请求创建一个新的DTO
class PresignedPolicyRequest(BaseModel):
    """为安全的POST预签名策略准备的请求体。"""
    original_filename: str = Field(..., description="用户上传的原始文件名。")
    content_type: str = Field(..., description="文件的MIME类型，例如 'image/jpeg'。")

class PresignedUploadPolicy(BaseModel):
    """
    用于返回预签名POST Policy的数据传输对象。
    它包含了前端直接向对象存储上传文件所需的所有信息。
    """

    url: str = Field(
        ...,
        description="前端必须向此URL以POST方法提交一个 multipart/form-data 表单。"
    )

    fields: Dict[str, Any] = Field(
        ...,
        description=(
            "一个包含所有必需表单字段的字典。前端在构建form-data时，"
            "必须将此字典中的每一个键值对都作为表单的一个字段。"
            "这些字段包含了加密的策略和签名，是上传成功的关键。"
        )
    )

    object_name: str = Field(
        ...,
        description="文件上传成功后，在存储桶中唯一的路径/键 (object_name)。"
    )

    final_url: str = Field(
        ...,
        description="文件上传成功后，最终可公开访问的URL。"
    )


class RegisterFilePayload(BaseModel):
    """
    用于“登记文件”接口的请求体模型。
    """
    object_name: str = Field(..., description="文件在云存储中唯一的 object_name")
    original_filename: str = Field(..., description="文件的原始名称")
    content_type: str = Field(..., description="文件的 MIME 类型")
    file_size: int = Field(..., description="文件大小（字节）")
    profile_name: str = Field(..., description="上传时使用的业务场景 Profile 名称")
    etag: Optional[str] = Field(None, description="文件上传后，由对象存储返回的 ETag")


class PresignedPolicyPayload(BaseModel):
    profile_name: str = Field(..., description="在配置中定义的 Profile 名称。")
    original_filename: str = Field(..., description="待上传文件的原始名称。")
    content_type: str = Field(..., description="待上传文件的MIME类型, e.g., 'image/jpeg'。")
    path_params: Optional[dict] = Field(default_factory=dict, description="用于格式化路径的动态参数。")
    expires_in: int = Field(3600, description="URL 有效期（秒）。")