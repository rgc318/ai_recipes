import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.dependencies.services import get_file_service # 【修改】建议将依赖注入函数重命名
from app.core.api_response import StandardResponse, response_success
from app.schemas.file_schemas import ( # 导入我们为返回值定义的 Pydantic 模型
    UploadResult,
    PresignedUploadURL
)
from app.services.file_service import FileService
from pydantic import BaseModel, Field


# ==============================================================================
#                      为请求体定义 Pydantic 模型
# ==============================================================================

class DeleteFilesPayload(BaseModel):
    profile_name: str = Field(..., description="文件所在存储的 Profile 名称。")
    object_names: List[str] = Field(..., min_length=1, description="需要删除的文件对象名称（key）列表。")

class PresignedPutUrlPayload(BaseModel):
    profile_name: str = Field(..., description="在配置中定义的 Profile 名称。")
    original_filename: str = Field(..., description="待上传文件的原始名称。")
    path_params: Optional[dict] = Field(default_factory=dict, description="用于格式化路径的动态参数。")
    expires_in: int = Field(3600, description="URL 有效期（秒）。")


# ==============================================================================
#                            API 路由定义
# ==============================================================================

router = APIRouter()

@router.post(
    "/upload/avatar",
    response_model=StandardResponse[UploadResult],
    summary="上传用户头像"
)
async def upload_user_avatar(
    user_id: str = Form(..., description="用户ID"),
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
):
    """
    上传用户头像。
    此端点内部硬编码使用 'user_avatars' profile。
    """
    result = await file_service.upload_user_avatar(file=file, user_id=user_id)
    return response_success(data=result, message="头像上传成功。")


@router.post(
    "/upload/by_profile",
    response_model=StandardResponse[UploadResult],
    summary="按业务场景上传文件 (通用)"
)
async def upload_by_profile(
    profile_name: str = Form(default="general_files", description="在配置中定义的 Profile 名称, e.g., 'secure_reports'"),
    path_params_json: str = Form("{}", description="用于格式化路径的动态参数 (JSON 字符串), e.g., '{\"tenant_id\": \"abc\"}'"),
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
):
    """
    通用的、由配置驱动的文件上传端点。
    """
    path_params = json.loads(path_params_json)
    result = await file_service.upload_by_profile(
        file=file,
        profile_name=profile_name,
        **path_params
    )
    return response_success(data=result, message="文件上传成功。")


@router.delete(
    "/files",
    status_code=204,
    summary="按 Profile 删除一个或多个文件"
)
async def delete_files_by_profile(
    payload: DeleteFilesPayload,
    file_service: FileService = Depends(get_file_service),
):
    """
    根据 Profile 和文件对象名称列表，从存储中删除一个或多个文件。
    """
    await file_service.delete_files(
        object_names=payload.object_names,
        profile_name=payload.profile_name
    )
    # 成功时，FastAPI 会自动发送 204 No Content 响应。


@router.get(
    "/files/exists",
    response_model=StandardResponse[bool],
    summary="按 Profile 检查文件是否存在"
)
async def check_file_exists_by_profile(
    profile_name: str = Query(..., description="文件所在存储的 Profile 名称。"),
    object_name: str = Query(..., description="需要检查的文件对象名称（key）。"),
    file_service: FileService = Depends(get_file_service),
):
    """根据 Profile 和文件对象名称检查文件是否存在。"""
    exists = await file_service.file_exists(
        object_name=object_name,
        profile_name=profile_name
    )
    return response_success(data=exists)


@router.get(
    "/presigned-url/get",
    response_model=StandardResponse[str],
    summary="按 Profile 生成用于下载的预签名 URL"
)
async def get_presigned_download_url_by_profile(
    profile_name: str = Query(..., description="文件所在存储的 Profile 名称。"),
    object_name: str = Query(..., description="文件的对象名称（key）。"),
    expires_in: int = Query(3600, description="URL 有效期（秒）。"),
    file_service: FileService = Depends(get_file_service),
):
    """为一个私有对象生成临时的、安全的文件下载 URL。"""
    url = await file_service.generate_presigned_get_url(
        object_name=object_name,
        profile_name=profile_name,
        expires_in=expires_in
    )
    return response_success(data=url)


@router.post(
    "/presigned-url/put",
    response_model=StandardResponse[PresignedUploadURL],
    summary="按 Profile 生成用于上传的预签名 URL"
)
async def get_presigned_upload_url_by_profile(
    payload: PresignedPutUrlPayload,
    file_service: FileService = Depends(get_file_service),
):
    """
    为客户端直接上传文件请求一个安全的、临时的 URL。
    服务器会根据 Profile 配置和动态参数生成唯一的对象名称。
    """
    result = await file_service.generate_presigned_put_url(
        profile_name=payload.profile_name,
        original_filename=payload.original_filename,
        expires_in=payload.expires_in,
        **payload.path_params
    )
    return response_success(data=result)


@router.get(
    "/files",
    response_model=StandardResponse[List[str]],
    summary="按 Profile 列出文件"
)
async def list_files_by_profile(
    profile_name: str = Query(..., description="要查询的存储 Profile 名称。"),
    prefix: str = Query("", description="按对象名称前缀筛选，例如 'avatars/user_id/'"),
    file_service: FileService = Depends(get_file_service),
):
    """根据 Profile 和前缀列出存储桶中的文件对象。"""
    files_list = await file_service.list_files(
        profile_name=profile_name,
        prefix=prefix
    )
    return response_success(data=files_list)
