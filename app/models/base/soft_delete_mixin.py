# app/models/base/soft_delete_mixin.py
from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field
from typing import Optional
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
