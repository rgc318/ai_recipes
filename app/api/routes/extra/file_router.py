import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.dependencies.permissions import require_verified_user
from app.api.dependencies.service_getters.common_service_getter import get_file_service, \
    get_file_record_service  # 【修改】建议将依赖注入函数重命名
from app.core.exceptions import BaseBusinessException
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.schemas.file.file_record_schemas import FileRecordRead
from app.schemas.file.file_schemas import (  # 导入我们为返回值定义的 Pydantic 模型
    UploadResult,
    PresignedUploadURL, RegisterFilePayload, PresignedUploadPolicy, PresignedPolicyPayload
)
from app.schemas.users.user_context import UserContext
from app.services.file.file_record_service import FileRecordService
from app.services.file.file_service import FileService
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
    current_user: UserContext = Depends(require_verified_user),
):
    """
    通用的、由配置驱动的文件上传端点。
    """
    path_params = json.loads(path_params_json)
    result = await file_service.upload_by_profile(
        file=file,
        profile_name=profile_name,
        uploader_context=current_user,
        **path_params
    )
    return response_success(data=result, message="文件上传并登记成功。")


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





@router.post(
    "/presigned-url/policy", # 建议使用 /policy 路径以作区分
    response_model=StandardResponse[PresignedUploadPolicy],
    summary="【安全模式】按 Profile 生成用于上传的预签名 POST 策略 (通用)",
    dependencies=[Depends(require_verified_user)] # 这是一个安全操作，建议加上权限校验
)
async def generate_presigned_upload_policy_by_profile(
    payload: PresignedPolicyPayload,
    file_service: FileService = Depends(get_file_service),
):
    """
    为客户端直接上传文件请求一个安全的、带策略的临时凭证。
    这是推荐的通用上传授权方法。
    """
    result = await file_service.generate_presigned_upload_policy(
        profile_name=payload.profile_name,
        original_filename=payload.original_filename,
        content_type=payload.content_type, # <--- 传递 content_type
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


@router.post(
    "/register",
    response_model=StandardResponse[FileRecordRead],
    summary="登记一个已通过预签名URL上传的文件"
)
async def register_file(
    payload: RegisterFilePayload,
    service: FileRecordService = Depends(get_file_record_service),
    current_user: UserContext = Depends(require_verified_user),
):
    """
    在文件成功上传到对象存储后，客户端调用此接口，
    在数据库中创建对应的 FileRecord 记录，并返回该记录的完整信息（包括ID）。
    """
    try:
        file_record_orm = await service.register_uploaded_file(
            object_name=payload.object_name,
            original_filename=payload.original_filename,
            content_type=payload.content_type,
            file_size=payload.file_size,
            profile_name=payload.profile_name,
            uploader_context=current_user,
            etag=payload.etag
        )
        # 登记成功后，可能需要填充动态URL再返回
        file_record_dto = await service.get_file_record_by_id(file_record_orm.id)
        return response_success(data=file_record_dto)
    except BaseBusinessException as e:
        return response_error(message=e.message)
