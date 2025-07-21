from pydantic import BaseModel, Field
from typing import List, Optional

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