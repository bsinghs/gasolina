"""Who is calling? Turns the request's sign-in token into a CurrentUser.

Sign-in itself (Google, email link) is done by Supabase Auth in the browser. The browser then
sends the token it got as `Authorization: Bearer <token>`. We verify it here and look the email
up in the `people` table. Anyone not in `people` (or deactivated) is refused.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException

from app.core import db
from app.core.config import get_settings


@dataclass
class CurrentUser:
    id: UUID
    email: str
    name: str
    role: str  # employee | manager | owner | admin
    store_ids: list[UUID] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        """The person who runs the app (support)."""
        return self.role == "admin"

    @property
    def is_owner(self) -> bool:
        """Has owner powers: the business owner, or an app admin."""
        return self.role in ("owner", "admin")

    def can_access_store(self, store_id: UUID) -> bool:
        return self.is_owner or store_id in self.store_ids


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True)


def _email_from_token(token: str) -> tuple[str, str | None, str | None]:
    """New Supabase projects sign tokens with a key pair (checked against the project's public keys).
    Older projects use a shared secret (HS256), which needs SUPABASE_JWT_SECRET."""
    settings = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise jwt.InvalidTokenError("HS256 token but SUPABASE_JWT_SECRET is not set")
            claims = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
        else:
            key = _jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["ES256", "RS256"], audience="authenticated")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Your sign-in has expired. Please sign in again.") from exc
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Sign-in token has no email")
    meta = claims.get("user_metadata") or {}
    full_name = (meta.get("full_name") or meta.get("name") or "").strip() or None
    return email, claims.get("sub"), full_name


def _is_placeholder_name(name: str, email: str) -> bool:
    """Names the app made up (first-owner bootstrap, admin from ADMIN_EMAILS), not ones a person typed."""
    return name.strip().lower() in {"owner", email.split("@")[0].lower()}


def _load_person(email: str, auth_user_id: str | None, full_name: str | None = None) -> CurrentUser:
    with db.transaction() as conn:
        person = db.fetch_one(
            conn, "select * from people where lower(email) = lower(%s) and active", [email]
        )
        if person is None:
            raise HTTPException(status_code=403, detail="not_invited")
        if auth_user_id and person["auth_user_id"] is None:
            db.execute(conn, "update people set auth_user_id = %s where id = %s", [auth_user_id, person["id"]])
        if full_name and _is_placeholder_name(person["name"], person["email"]):
            # Use the name from their Google account instead of a made-up one
            db.execute(conn, "update people set name = %s where id = %s", [full_name[:120], person["id"]])
            person["name"] = full_name[:120]
        stores = db.fetch_all(conn, "select store_id from store_members where person_id = %s", [person["id"]])
    return CurrentUser(
        id=person["id"],
        email=person["email"],
        name=person["name"],
        role=person["role"],
        store_ids=[s["store_id"] for s in stores],
    )


def current_user(
    authorization: str | None = Header(default=None),
    x_dev_email: str | None = Header(default=None),
) -> CurrentUser:
    settings = get_settings()
    if settings.auth_mode == "dev" and x_dev_email:
        return _load_person(x_dev_email, None)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in")
    email, sub, full_name = _email_from_token(authorization.split(" ", 1)[1])
    return _load_person(email, sub, full_name)


def owner_only(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not user.is_owner:
        raise HTTPException(status_code=403, detail="Only the owner can do this")
    return user


def bootstrap_owner() -> None:
    """Make sure BOOTSTRAP_OWNER_EMAIL exists as an owner, so the very first sign-in works."""
    settings = get_settings()
    if not settings.bootstrap_owner_email:
        return
    with db.transaction() as conn:
        db.execute(
            conn,
            """insert into people (email, name, role) values (%s, %s, 'owner')
               on conflict (lower(email)) do nothing""",
            [settings.bootstrap_owner_email, settings.bootstrap_owner_name],
        )


def bootstrap_admins() -> None:
    """Make sure everyone in ADMIN_EMAILS exists, is active and has the admin role."""
    emails = get_settings().admin_email_list
    if not emails:
        return
    with db.transaction() as conn:
        for email in emails:
            db.execute(
                conn,
                """insert into people (email, name, role) values (%s, %s, 'admin')
                   on conflict (lower(email)) do update set role = 'admin', active = true""",
                [email, email.split("@")[0]],
            )
