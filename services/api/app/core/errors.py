"""Short helpers so modules raise clear HTTP errors in one line."""

from fastapi import HTTPException


def not_found(what: str = "Not found") -> HTTPException:
    return HTTPException(status_code=404, detail=what)


def forbidden(why: str = "You don't have access to this") -> HTTPException:
    return HTTPException(status_code=403, detail=why)


def bad_request(why: str) -> HTTPException:
    return HTTPException(status_code=400, detail=why)


def conflict(why: str) -> HTTPException:
    return HTTPException(status_code=409, detail=why)
