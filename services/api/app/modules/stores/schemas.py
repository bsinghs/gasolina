from uuid import UUID

from pydantic import BaseModel, Field, field_validator

DEFAULT_TANKS = ["Tank 1 – Regular", "Tank 2 – Regular", "Tank 3 – Premium"]


class StoreIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    qb_location: str | None = Field(default=None, max_length=120)
    active: bool = True
    # Underground fuel tanks, in the order employees read them at closing. None = keep as is (default for new stores)
    tanks: list[str] | None = Field(default=None, max_length=10)

    @field_validator("tanks")
    @classmethod
    def clean_tanks(cls, tanks: list[str] | None) -> list[str] | None:
        if tanks is None:
            return None
        cleaned, seen = [], set()
        for t in tanks:
            t = " ".join(t.split())[:60]
            if t and t.lower() not in seen:
                cleaned.append(t)
                seen.add(t.lower())
        if not cleaned:
            raise ValueError("Give the store at least one tank")
        return cleaned


class Store(StoreIn):
    id: UUID
    tanks: list[str] = DEFAULT_TANKS
