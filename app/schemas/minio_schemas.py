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