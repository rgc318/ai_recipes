from sqlmodel import SQLModel, Field
from sqlalchemy.ext.declarative import declared_attr
import uuid
import re
from app.models.base.timestamp_mixin import TimestampMixin
from app.models.base.audit_mixin import AuditMixin
from app.models.base.soft_delete_mixin import SoftDeleteMixin
from app.models._model_utils.guid import GUID

def camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

class AutoTableNameMixin:
    @declared_attr
    def __tablename__(cls):
        name = camel_to_snake(cls.__name__)
        print(f"Calculating tablename for {cls.__name__}: {name}")
        return camel_to_snake(cls.__name__)

class BaseModel(SQLModel, AutoTableNameMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __abstract__ = True  # 防止BaseModel本身成为表

    id: uuid.UUID = Field(default_factory=GUID.generate, sa_type=GUID(), primary_key=True, index=True)

