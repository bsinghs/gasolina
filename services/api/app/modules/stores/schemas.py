from uuid import UUID

from pydantic import BaseModel, Field


class StoreIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    qb_location: str | None = Field(default=None, max_length=120)
    active: bool = True


class Store(StoreIn):
    id: UUID
