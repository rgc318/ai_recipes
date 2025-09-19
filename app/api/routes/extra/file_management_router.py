from typing import Optional, List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status, Body

from app.core.exceptions import BaseBusinessException
from app.enums.query_enums import ViewMode
from app.schemas.common.api_response import StandardResponse, response_success, response_error
from app.enums.response_codes import ResponseCodeEnum
from app.schemas.common.page_schemas import PageResponse
from app.schemas.file.file_record_schemas import FileRecordRead, FileRecordUpdate, FileFilterParams, BulkActionPayload
from app.services.file.file_record_service import FileRecordService
from app.api.dependencies.service_getters.common_service_getter import get_file_record_service # 假设您会创建一个对应的依赖注入函数

# ==============================================================================
#                            API 路由定义
# ==============================================================================

router = APIRouter()


@router.post(
    "/{record_id}/restore",
    response_model=StandardResponse[FileRecordRead],
    summary="【管理员】恢复一个被软删除的文件记录"
)
async def restore_file_record(
    record_id: UUID,
    service: FileRecordService = Depends(get_file_record_service)
):
    """
    从软删除状态（回收站）中恢复一条文件记录。
    """
    restored_record = await service.restore_file_record(record_id)
    if not restored_record:
        return response_error(message="文件记录不存在或未被删除", code=ResponseCodeEnum.NOT_FOUND)
    return response_success(data=restored_record, message="文件记录已恢复")


@router.post(
    "/restore/bulk",
    response_model=StandardResponse[Dict[str, int]],
    summary="【管理员】批量恢复文件记录"
)
async def restore_files_in_bulk(
        record_ids: List[UUID] = Body(..., embed=True),
        service: FileRecordService = Depends(get_file_record_service)
):
    """
    根据提供的ID列表，批量恢复被软删除的文件记录。
    """
    restored_count = await service.restore_file_records_by_ids(record_ids)
    return response_success(data={"restored_count": restored_count}, message="批量恢复操作完成")


@router.delete(
        "/bulk/soft",
        response_model=StandardResponse[Dict[str, int]],
        summary="【管理员】批量软删除文件记录"
        )
async def soft_delete_files_in_bulk(
    payload: BulkActionPayload,
    service: FileRecordService = Depends(get_file_record_service)
):
    """
    根据提供的ID列表，将多条文件记录批量移入回收站。
    """
    deleted_count = await service.soft_delete_records_by_ids(payload.record_ids)
    return response_success(data={"deleted_count": deleted_count}, message="批量软删除操作完成")

@router.delete(
        "/bulk/permanent",
        response_model=StandardResponse[Dict[str, int]],
        summary="【管理员】批量彻底删除文件记录（高危）"
    )
async def permanently_delete_files_in_bulk(
    payload: BulkActionPayload,
    service: FileRecordService = Depends(get_file_record_service)
):
    """
    根据提供的ID列表，批量、永久地删除文件记录及其对应的物理文件。
    这是一个高风险操作。
    """
    try:
        # [MODIFIED] - 在执行删除前，先调用验证方法
        await service.validate_records_for_permanent_delete(payload.record_ids)

        # 验证通过后，才执行实际的删除操作
        deleted_count = await service.permanent_delete_records_by_ids(payload.record_ids)
        return response_success(data={"deleted_count": deleted_count}, message="批量永久删除操作完成")

    except BaseBusinessException as e:
        # 捕获我们自己抛出的业务异常，并将其作为友好的错误信息返回给前端
        return response_error(message=str(e), code=ResponseCodeEnum.FILE_IN_USE_ERROR)

@router.delete(
    "/{record_id}/permanent",
    response_model=StandardResponse[None],
    status_code=status.HTTP_200_OK,
    summary="【管理员】彻底删除一个文件（协同删除）"
)
async def permanently_delete_file(
        record_id: UUID,
        service: FileRecordService = Depends(get_file_record_service)
):
    """
    一个高危操作！
    此端点会先从对象存储中删除真实文件，然后从数据库中物理删除记录。
    """
    if await service.is_record_in_use(record_id):
        return response_error(
            message="此文件正被一个或多个业务使用（如菜谱封面、用户头像等），无法删除。请先解除关联。",
        )

    # delete_file_and_record 需要 FileRecord 对象，所以我们先获取它
    # 注意：需要从所有视图中查找，因为它可能已被软删除
    record = await service.file_repo.get_by_id(record_id, view_mode='all')
    if not record:
        return response_error(message="文件记录不存在", code=ResponseCodeEnum.NOT_FOUND)

    await service.delete_file_and_record(record, hard_delete_db=True)
    return response_success(data=None, message="文件已被彻底删除")


@router.post(
    "/merge",
    response_model=StandardResponse[FileRecordRead],
    summary="【管理员】合并重复的文件记录"
)
async def merge_files(
        source_id: UUID = Body(...),
        target_id: UUID = Body(...),
        service: FileRecordService = Depends(get_file_record_service)
):
    """
    将源记录(source_id)的引用合并到目标记录(target_id)后，物理删除源记录。
    这是一个数据清理的高级功能。
    """
    merged_record = await service.merge_duplicate_records(source_id, target_id)
    return response_success(data=merged_record, message="文件记录合并成功")


@router.get(
    "/stats",
    response_model=StandardResponse,  # 类型取决于 service 返回值
    summary="【管理员】获取文件存储统计"
)
async def get_storage_statistics(
        group_by: Optional[str] = Query(None, description="分组依据, 如: uploader_id, profile_name"),
        service: FileRecordService = Depends(get_file_record_service)
):
    """

    获取文件存储的使用情况统计，可按上传者或Profile分组。
    用于管理员仪表盘。
    """
    stats = await service.get_storage_stats(group_by=group_by)
    return response_success(data=stats)

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
    view_mode: ViewMode = Query(
        default=ViewMode.ACTIVE, # 默认只看活跃的
        description="数据视图模式：'active' (活跃), 'deleted' (已删除), 'all' (全部)"
    )
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

        if value:  # 这个判断同时处理了 None 和空字符串 "" 的情况
            filters["original_filename__ilike"] = f"%{value}%"

    page_data = await service.get_paged_file_records(
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        filters=filters,
        view_mode=view_mode
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
