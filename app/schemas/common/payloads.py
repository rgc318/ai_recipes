# in a file like app/schemas/common/payloads.py
from typing import List
from uuid import UUID
from pydantic import BaseModel

class BatchAddImagesPayload(BaseModel):
    file_record_ids: List[UUID]