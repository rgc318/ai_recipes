from sqlmodel import SQLModel, Field
from typing import Optional

class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] =  None
    ingredients: str
    steps: str