# app/types/common.py
from typing import TypeVar

from pydantic import BaseModel
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)
T = TypeVar("T", bound=BaseModel)