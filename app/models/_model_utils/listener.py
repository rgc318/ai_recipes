from sqlalchemy import event
from sqlalchemy.orm import Mapper
from datetime import datetime

from app.models.recipe import BaseModel  # 替换为你的实际基类

@event.listens_for(BaseModel, "before_update", propagate=True)
def auto_update_updated_at(mapper: Mapper, connection, target: BaseModel):
    target.updated_at = datetime.utcnow()