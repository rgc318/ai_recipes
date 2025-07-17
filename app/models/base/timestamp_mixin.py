# app/models/base/timestamp_mixin.py
from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

from app.models._model_utils.datetime import NaiveDateTime, get_utc_now, utcnow


class TimestampMixin:
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )