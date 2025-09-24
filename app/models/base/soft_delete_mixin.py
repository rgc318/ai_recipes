# app/models/base/soft_delete_mixin.py
from sqlalchemy import DateTime, Index, Column
from sqlmodel import SQLModel, Field
from typing import Optional, Tuple, Iterable, Union
from datetime import datetime
import uuid

from app.models._model_utils.datetime import utcnow
from app.models._model_utils.guid import GUID

class SoftDeleteMixin:
    is_deleted: bool = Field(default=False, index=True)
    deleted_at: Optional[datetime] = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True)
    )
    deleted_by: Optional[uuid.UUID] = Field(default=None, sa_type=GUID(), index=True)

    @classmethod
    def soft_unique_index(
        cls,
        table_name: str,

        *columns: Union[str, Iterable[str]],
        batch: bool = False
    ) -> Tuple[Index, ...]:
        """
        为当前模型生成软删除唯一索引

        :param columns: 列名，支持多个列组合索引，或批量生成多个单列索引
        :param batch: 如果为 True，则为每个列生成单独的软删除唯一约束
        :return: tuple(Index(...), ...)
        """
        # if not hasattr(cls, "__tablename__"):
        #     raise RuntimeError(f"{cls.__name__} 没有 __tablename__，无法生成索引")

        indexes = []
        flat_columns = []

        if batch:
            # 为每个列单独生成一个索引
            for col in columns:
                if isinstance(col, Iterable) and not isinstance(col, str):
                    col = list(col)  # 如果传入集合，展开
                else:
                    col = [col]

                index_name = f"ix_{table_name}_{'_'.join(col)}_active_unique"
                indexes.append(
                    Index(
                        index_name,
                        *col,
                        unique=True,
                        postgresql_where=(Column("is_deleted") == False)
                    )
                )
        else:
            # 单个联合索引
            flat_columns = []
            for col in columns:
                if isinstance(col, Iterable) and not isinstance(col, str):
                    flat_columns.extend(col)
                else:
                    flat_columns.append(col)

            if flat_columns:
                index_name = f"ix_{table_name}_{'_'.join(flat_columns)}_active_unique"
                indexes.append(
                    Index(
                        index_name,
                        *flat_columns,
                        unique=True,
                        postgresql_where=(Column("is_deleted") == False)
                    )
                )

        return tuple(indexes)
