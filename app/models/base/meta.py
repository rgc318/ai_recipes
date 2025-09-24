from sqlalchemy import Index, Column
from sqlmodel.main import SQLModelMetaclass

from app.models.base.soft_delete_mixin import SoftDeleteMixin


class SoftDeleteUniqueMeta(SQLModelMetaclass):
    def __new__(mcs, name, bases, attrs, **kwargs):
        return super().__new__(mcs, name, bases, attrs, **kwargs)

    def __init__(cls, name, bases, attrs, **kwargs):
        super().__init__(name, bases, attrs, **kwargs)

        # 只处理带 SoftDeleteMixin 的类
        if not any(issubclass(base, SoftDeleteMixin) for base in bases):
            return

        if not hasattr(cls, "__table__"):
            return

        table_args = list(getattr(cls, "__table_args__", ()))

        for col in cls.__table__.columns:
            if col.unique:
                col.unique = False
                index_name = f'ix_{cls.__tablename__}_{col.name}_active_unique'
                new_index = Index(
                    index_name,
                    col,
                    unique=True,
                    postgresql_where=(cls.__table__.c.is_deleted == False),
                )
                table_args.append(new_index)

        cls.__table_args__ = tuple(table_args)
