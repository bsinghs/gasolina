from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# fuel / merchandise = cost of goods (what you buy to sell); expense = everything else
Kind = Literal["fuel", "merchandise", "expense"]


class VendorIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Kind
    active: bool = True

    @field_validator("name")
    @classmethod
    def tidy(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the vendor a name")
        return v


class Vendor(VendorIn):
    id: UUID
    used: bool = False   # has typed purchases/expenses (then it can only be deactivated)
