from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_TANKS = ["Tank 1 – Regular", "Tank 2 – Regular", "Tank 3 – Premium"]
Grade = Literal["Regular", "Plus", "Premium", "Diesel", "Other"]
GRADES: tuple[str, ...] = Grade.__args__


def guess_grade(tank_name: str) -> str:
    """Starting fuel type from the tank's name ("Tank 3 – Premium" → Premium) until the owner sets it."""
    n = tank_name.lower()
    for word, grade in (("premium", "Premium"), ("diesel", "Diesel"), ("plus", "Plus"), ("mid", "Plus"), ("super", "Premium")):
        if word in n:
            return grade
    return "Regular"


def tidy_tank_names(names: list[str]) -> list[str]:
    cleaned, seen = [], set()
    for t in names:
        t = " ".join(t.split())[:60]
        if t and t.lower() not in seen:
            cleaned.append(t)
            seen.add(t.lower())
    if not cleaned:
        raise ValueError("Give the store at least one tank")
    return cleaned


class TankSpec(BaseModel):
    """One underground tank: its name (as on the worksheet), fuel type and size."""

    name: str = Field(min_length=1, max_length=60)
    grade: Grade = "Regular"
    capacity: Decimal | None = Field(default=None, gt=0, le=100000, decimal_places=0)  # gallons; None = unknown
    # Sent when the owner renames a tank, so its past readings and deliveries (saved under the old name) stay with it
    previous_name: str | None = Field(default=None, max_length=60)


class TankSpecOut(BaseModel):
    name: str
    grade: str
    capacity: Decimal | None = None
    aliases: list[str] = []  # older names of this tank (its history is kept under them)


def specs_for(tanks: list[str], stored: dict | None) -> list[dict]:
    """The store's tanks in order, each with its saved fuel type / capacity (or a guess from the name)."""
    stored = stored or {}
    out = []
    for name in tanks:
        s = stored.get(name) or {}
        out.append({"name": name, "grade": s.get("grade") or guess_grade(name), "capacity": s.get("capacity"),
                    "aliases": list(s.get("aliases") or [])})
    return out


class StoreIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    qb_location: str | None = Field(default=None, max_length=120)
    active: bool = True
    # Underground fuel tanks, in the order employees read them at closing. None = keep as is (default for new stores)
    tanks: list[str] | None = Field(default=None, max_length=10)
    # Same tanks with fuel type and capacity (Settings). When sent, it decides the tank list too
    tank_specs: list[TankSpec] | None = Field(default=None, max_length=10)

    @field_validator("tanks")
    @classmethod
    def clean_tanks(cls, tanks: list[str] | None) -> list[str] | None:
        return None if tanks is None else tidy_tank_names(tanks)

    @model_validator(mode="after")
    def specs_decide_tanks(self) -> "StoreIn":
        if self.tank_specs is not None:
            names = tidy_tank_names([s.name for s in self.tank_specs])
            by_name = {}
            for s in self.tank_specs:
                key = " ".join(s.name.split())[:60]
                if key in names and key not in by_name:
                    prev = " ".join(s.previous_name.split())[:60] if s.previous_name else None
                    by_name[key] = TankSpec(name=key, grade=s.grade, capacity=s.capacity, previous_name=prev)
            self.tank_specs = [by_name[n] for n in names]
            self.tanks = names
        return self

    def specs_json(self, stored: dict | None = None) -> dict | None:
        """{name: {grade, capacity, aliases}} to store, or None to keep what's saved. A renamed tank
        (previous_name) carries its old names along, so Inventory still finds its history."""
        if self.tank_specs is None:
            return None
        stored = stored or {}
        out = {}
        for s in self.tank_specs:
            source = s.previous_name if s.previous_name and s.previous_name in stored else s.name
            aliases = list((stored.get(source) or {}).get("aliases") or [])
            if s.previous_name and s.previous_name != s.name and s.previous_name not in aliases:
                aliases.append(s.previous_name)
            out[s.name] = {"grade": s.grade, "capacity": int(s.capacity) if s.capacity else None,
                           "aliases": [a for a in aliases if a != s.name][:20]}
        return out


class Store(BaseModel):
    id: UUID
    name: str
    qb_location: str | None = None
    active: bool = True
    tanks: list[str] = DEFAULT_TANKS
    tank_specs: list[TankSpecOut] = []
