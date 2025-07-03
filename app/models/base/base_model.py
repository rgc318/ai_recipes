# app/models/base/base_model.py
from sqlmodel import SQLModel, Field
import uuid
from app.models.base.timestamp_mixin import TimestampMixin
from app.models.base.audit_mixin import AuditMixin
from app.models.base.soft_delete_mixin import SoftDeleteMixin
from app.models._model_utils.guid import GUID

class BaseModel(SQLModel, TimestampMixin, AuditMixin, SoftDeleteMixin):
    id: uuid.UUID = Field(default_factory=GUID.generate, sa_type=GUID(), primary_key=True, index=True)
