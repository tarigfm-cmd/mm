import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class MaterialResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    file_name: str
    file_size: int
    file_type: str
    content_text: Optional[str] = None
    has_content: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialListItem(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    file_name: str
    file_size: int
    file_type: str
    has_content: bool
    scenario_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    items: List[MaterialListItem]
    total: int
    page: int
    per_page: int
    pages: int
