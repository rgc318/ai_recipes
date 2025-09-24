from sqlalchemy import Column, Integer, String, Boolean, Index
from sqlalchemy.orm import declarative_base, declared_attr

Base = declarative_base()

class SoftUniqueMixin:
    is_deleted = Column(Boolean, default=False, nullable=False)

    @declared_attr
    def __table_args__(cls):
        indexes = []
        for col in cls.__table__.columns:
            if getattr(col, "soft_unique", False):  # 👈 判断自定义属性
                indexes.append(
                    Index(
                        f"ix_{cls.__tablename__}_{col.name}_active_unique",
                        col,
                        unique=True,
                        postgresql_where=cls.is_deleted.is_(False)
                    )
                )
        return tuple(indexes)
