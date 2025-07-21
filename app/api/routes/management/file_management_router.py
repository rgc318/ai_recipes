from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status

from app.core.api_response import StandardResponse, response_success, response_error
from app.core.response_codes import ResponseCodeEnum
from app.schemas.page_schemas import PageResponse
from app.schemas.file_record_schemas import FileRecordRead, FileRecordUpdate, FileFilterParams
from app.services.file_record_service import FileRecordService
from app.api.dependencies.services import get_file_record_service # 假设您会创建一个对应的依赖注入函数
from pydantic import BaseModel, Field


# ==============================================================================
#                            API 路由定义
# ==============================================================================

router = APIRouter()

@router.get(
    "/",
    response_model=StandardResponse[PageResponse[FileRecordRead]],
    summary="动态分页、排序和过滤文件记录列表"
)
async def list_file_records_paginated(
    service: FileRecordService = Depends(get_file_record_service),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(10, ge=1, le=100, description="每页数量"),
    sort: Optional[str] = Query(
        "-created_at",
        description="排序字段，逗号分隔，-号表示降序。例如: -created_at,original_filename",
    ),
    filter_params: FileFilterParams = Depends(),
):
    """
    获取文件记录的分页列表，为文件管理系统提供核心数据支持。

    - **排序**: `?sort=-file_size,original_filename`
    - **过滤**: `?profile_name=user_avatars&content_type=image/png`
    """
    sort_by = sort.split(',') if sort else None
    filters = filter_params.model_dump(exclude_unset=True)

    # 将前端友好的查询转为后端Repo能理解的指令
    if "original_filename" in filters:
        value = filters.pop("original_filename")
        filters["original_filename__ilike"] = f"%{value}%"

    page_data = await service.get_paged_file_records(
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        filters=filters
    )

    return response_success(data=page_data, message="获取文件列表成功")


@router.get(
    "/{record_id}",
    response_model=StandardResponse[FileRecordRead],
    summary="获取单个文件记录详情"
)
async def get_file_record_details(
    record_id: UUID,
    service: FileRecordService = Depends(get_file_record_service)
):
    """
    根据文件记录的数据库ID，获取其完整的元数据信息，包括动态生成的URL。
    """
    file_record = await service.get_file_record_by_id(record_id)
    if not file_record:
        # 在实际项目中，这里应该返回一个标准化的 not_found 响应
        return response_error(message="文件记录不存在", code=ResponseCodeEnum.FILE_EXCEPTION)
    return response_success(data=file_record)


@router.put(
    "/{record_id}",
    response_model=StandardResponse[FileRecordRead],
    summary="更新文件记录元数据"
)
async def update_file_record_metadata(
    record_id: UUID,
    updates: FileRecordUpdate,
    service: FileRecordService = Depends(get_file_record_service)
):
    """
    更新一个已存在的文件记录的元数据，例如修改其原始文件名。
    """
    updated_record = await service.update_file_record(record_id, updates)
    if not updated_record:
        return response_error(message="文件记录不存在", code=ResponseCodeEnum.FILE_EXCEPTION)
    return response_success(data=updated_record, message="文件信息更新成功")


@router.delete(
    "/{record_id}",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="软删除一个文件记录"
)
async def delete_file_record(
    record_id: UUID,
    service: FileRecordService = Depends(get_file_record_service)
):
    """
    软删除一条文件记录。
    注意：此操作仅在数据库中标记为删除，不会删除对象存储中的物理文件。
    """
    success = await service.delete_file_record(record_id)
    if not success:
        return response_error(message="文件记录不存在", code=ResponseCodeEnum.FILE_EXCEPTION)
    return response_success(data=None, message="文件记录已删除")
