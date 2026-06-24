from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class TagUpdate(BaseModel):
    name: str | None = None

class TagOut(TagBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)