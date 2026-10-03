from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

Role = Literal["employee", "manager", "owner"]


class PersonIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: Role = "employee"
    active: bool = True
    store_ids: list[UUID] = Field(default_factory=list)


class Person(BaseModel):
    id: UUID
    email: str
    name: str
    role: Role
    active: bool
    store_ids: list[UUID]
    has_signed_in: bool
