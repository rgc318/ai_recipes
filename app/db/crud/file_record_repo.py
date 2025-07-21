from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud.base_repo import BaseRepository
from app.models.file_record import FileRecord
from app.schemas.file_record_schemas import FileRecordCreate, FileRecordUpdate


class FileRecordRepository(BaseRepository[FileRecord, FileRecordCreate, FileRecordUpdate]):
    """
    FileRecordRepository 提供了所有与文件记录数据库操作相关的方法。
    它继承了 BaseRepository 的所有通用功能，并添加了文件记录特有的查询。
    """
    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        """
        初始化 FileRecordRepository。

        Args:
            db (AsyncSession): 数据库会话。
            context (Optional[dict]): 可选的上下文信息。
        """
        super().__init__(db, FileRecord, context)

    async def get_by_object_name(self, object_name: str) -> Optional[FileRecord]:
        """
        根据文件在对象存储中的唯一路径 (object_name) 获取文件记录。

        这是一个核心的查询方法，用于将存储对象与其元数据关联起来。

        Args:
            object_name (str): 文件在对象存储中的完整路径。

        Returns:
            Optional[FileRecord]: 找到的文件记录对象，如果不存在则返回 None。
        """
        # 使用继承的 get_one 方法，它已经处理了 is_deleted 逻辑和异常
        return await self.get_one(value=object_name, field="object_name")

    async def soft_delete_by_object_name(self, object_name: str) -> Optional[FileRecord]:
        """
        根据 object_name 软删除一个文件记录。

        这是一个便捷方法，封装了“先查找，再软删除”的常见操作。

        Args:
            object_name (str): 要软删除的文件的 object_name。

        Returns:
            Optional[FileRecord]: 被软删除的文件记录对象，如果未找到则返回 None。
        """
        db_obj = await self.get_by_object_name(object_name)
        if db_obj:
            return await self.soft_delete(db_obj)
        return None

    # --- 如何使用强大的分页查询 ---
    #
    # 您的 BaseRepository.get_paged_list 方法已经非常强大。
    # 您无需在此处编写新的分页方法，只需在 Service 层像这样调用它即可：
    #
    # file_repo = repo_factory.get_repo(FileRecordRepository)
    #
    # # 示例1: 查找某个用户上传的所有文件，按创建时间降序排序
    # user_files_page = await file_repo.get_paged_list(
    #     page=1,
    #     per_page=20,
    #     filters={"uploader_id": current_user.id},
    #     sort_by=["-created_at"]
    # )
    #
    # # 示例2: 查找所有通过 'secure_reports' Profile 上传的 PDF 文件
    # report_files_page = await file_repo.get_paged_list(
    #     page=1,
    #     per_page=50,
    #     filters={
    #         "profile_name": "secure_reports",
    #         "content_type": "application/pdf"
    #     }
    # )
    #
    # # 示例3: 使用更复杂的过滤器，查找文件名包含 "invoice" 的记录
    # invoice_files = await file_repo.get_paged_list(
    #     page=1,
    #     per_page=10,
    #     filters={"original_filename__ilike": "%invoice%"} # 使用 ilike 进行模糊搜索
    # )

