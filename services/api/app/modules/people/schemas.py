from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

Role = Literal["employee", "manager", "owner"]  # what the owner can give someone
ListedRole = Literal["employee", "manager", "owner", "admin"]  # admin comes from ADMIN_EMAILS only


class PersonIn(BaseModel):
    email: EmailStr
    # Optional: left blank, it's filled from their Google account the first time they sign in
    name: str = Field(default="", max_length=120)
    role: Role = "employee"
    active: bool = True
    store_ids: list[UUID] = Field(default_factory=list)


class Person(BaseModel):
    id: UUID
    email: str
    name: str
    role: ListedRole
    active: bool
    store_ids: list[UUID]
    has_signed_in: bool
