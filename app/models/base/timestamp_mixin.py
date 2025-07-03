# app/models/base/timestamp_mixin.py
from sqlmodel import SQLModel, Field
from datetime import datetime

class TimestampMixin:
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )
