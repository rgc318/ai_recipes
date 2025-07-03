# app/models/base/audit_mixin.py
from sqlmodel import SQLModel, Field
from typing import Optional
import uuid
from app.models._model_utils.guid import GUID

class AuditMixin:
    created_by: Optional[uuid.UUID] = Field(default=None, sa_type=GUID(), index=True)
    updated_by: Optional[uuid.UUID] = Field(default=None, sa_type=GUID(), index=True)
