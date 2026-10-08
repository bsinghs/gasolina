"""Money stays exact on the way out: Decimals become strings ("3518.33"), never floats (project rule 2)."""

from decimal import Decimal


def exact(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(v) for v in value]
    return value
