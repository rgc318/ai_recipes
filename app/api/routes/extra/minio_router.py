from fastapi import APIRouter, UploadFile, Form, File, Query, Depends, Body
from typing import List, Optional

# 导入依赖注入函数和新的 Schema
from app.api.dependencies.services import get_minio_service
from app.services.minio_service import MinioService
from app.schemas.minio_schemas import (
    FileUploadResponse,
    FileExistsResponse,
    FileListResponse,
    PresignedGetUrlResponse,
    PresignedPutUrlResponse,
)
from app.core.api_response import StandardResponse, response_success

router = APIRouter()

@router.post(
    "/upload/avatar",
    response_model=StandardResponse[FileUploadResponse],
    summary="上传用户头像"
)
async def upload_avatar(
    user_id: str = Form(..., description="用户ID"),
    file: UploadFile = File(...),
    minio_service: MinioService = Depends(get_minio_service),
):
    """
    上传用户头像。服务层会处理文件验证、重命名和并发控制。
    """
    # 所有的 try/except 都消失了！Service 层会抛出 FileException，
    # 由全局异常处理器统一捕获并返回格式化的错误响应。
    result = await minio_service.upload_user_avatar(file=file, user_id=user_id)
    return response_success(data=result, message="头像上传成功。")

@router.post(
    "/upload/file",
    response_model=StandardResponse[FileUploadResponse],
    summary="上传通用文件"
)
async def upload_general_file(
    folder: str = Form("general", description="在存储桶内的目标文件夹"),
    file: UploadFile = File(...),
    minio_service: MinioService = Depends(get_minio_service),
):
    """上传一个通用文件到指定的文件夹。"""
    result = await minio_service.upload_file(file=file, folder=folder, file_type="file")
    return response_success(data=result, message="文件上传成功。")

@router.delete(
    "/files",
    status_code=204,
    summary="删除一个或多个文件"
)
async def delete_files(
    object_names: List[str] = Body(..., description="需要删除的文件对象名称（key）列表。", embed=True),
    minio_service: MinioService = Depends(get_minio_service),
):
    """根据文件对象名称（key）从存储中删除一个或多个文件。"""
    await minio_service.delete_files(object_names=object_names)
    # 成功时，FastAPI 会自动发送 204 No Content 响应。

@router.get(
    "/files/exists",
    response_model=StandardResponse[FileExistsResponse],
    summary="检查文件是否存在"
)
async def check_file_exists(
    object_name: str = Query(..., description="需要检查的文件对象名称（key）。"),
    minio_service: MinioService = Depends(get_minio_service),
):
    """根据文件对象名称（key）检查文件是否存在。"""
    exists = await minio_service.file_exists(object_name=object_name)
    return response_success(data={"exists": exists})

@router.get(
    "/presigned-url/get",
    response_model=StandardResponse[PresignedGetUrlResponse],
    summary="生成用于下载文件的预签名 URL"
)
async def get_presigned_download_url(
    object_name: str = Query(..., description="文件的对象名称（key）。"),
    expires_in: int = Query(3600, description="URL 有效期（秒）。"),
    minio_service: MinioService = Depends(get_minio_service),
):
    """为一个私有对象生成临时的、安全的文件下载 URL。"""
    url = await minio_service.generate_presigned_get_url(object_name=object_name, expires_in=expires_in)
    return response_success(data={"url": url})

@router.post(
    "/presigned-url/put",
    response_model=StandardResponse[PresignedPutUrlResponse],
    summary="生成用于上传文件的预签名 URL"
)
async def get_presigned_upload_url(
    folder: str = Body("uploads", description="上传的目标文件夹。"),
    original_filename: str = Body(..., description="待上传文件的原始名称。"),
    expires_in: int = Body(3600, description="URL 有效期（秒）。"),
    minio_service: MinioService = Depends(get_minio_service),
):
    """
    为客户端直接上传文件，请求一个安全的、临时的 URL。
    服务层会生成唯一的对象名称以防止文件被覆盖。
    """
    result = await minio_service.generate_presigned_put_url(
        folder=folder,
        original_filename=original_filename,
        expires_in=expires_in
    )
    return response_success(data=result)

@router.get(
    "/files",
    response_model=StandardResponse[FileListResponse],
    summary="列出文件"
)
async def list_files(
    prefix: str = Query("", description="按对象名称前缀筛选，例如 'avatars/user_id/'"),
    minio_service: MinioService = Depends(get_minio_service),
):
    """根据前缀列出存储桶中的文件对象。"""
    files_list = await minio_service.list_files(prefix=prefix)
    return response_success(data={"files": files_list})