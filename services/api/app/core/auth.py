"""Who is calling? Turns the request's sign-in token into a CurrentUser.

Sign-in itself (Google, email link) is done by Supabase Auth in the browser. The browser then
sends the token it got as `Authorization: Bearer <token>`. We verify it here and look the email
up in the `people` table. Anyone not in `people` (or deactivated) is refused.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request

from app.core import db
from app.core.config import get_settings


OWNER_ROLES = ("owner", "coowner", "admin")  # roles with owner powers (see all stores, review, books)


@dataclass
class CurrentUser:
    id: UUID
    email: str
    name: str
    role: str  # employee | manager | owner | coowner | admin
    store_ids: list[UUID] = field(default_factory=list)
    # Set when the app admin is looking at the app as this person ("View as", read-only)
    viewed_by: "CurrentUser | None" = None

    @property
    def is_admin(self) -> bool:
        """The person who runs the app (support)."""
        return self.role == "admin"

    @property
    def is_owner(self) -> bool:
        """Has owner powers: the business owner, a co-owner, or an app admin."""
        return self.role in OWNER_ROLES

    @property
    def is_full_owner(self) -> bool:
        """May manage owners and co-owners: the owner or the app admin (not a co-owner)."""
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


def _signed_in_user(authorization: str | None, x_dev_email: str | None) -> CurrentUser:
    settings = get_settings()
    if settings.auth_mode == "dev" and x_dev_email:
        return _load_person(x_dev_email, None)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in")
    email, sub, full_name = _email_from_token(authorization.split(" ", 1)[1])
    return _load_person(email, sub, full_name)


READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}


def _view_as(admin: CurrentUser, person_id: str, method: str) -> CurrentUser:
    """App admin sees the app exactly as another person does. Read-only, so nothing is ever
    saved, submitted or approved under someone else's name."""
    if not admin.is_admin:
        raise HTTPException(status_code=403, detail="Only the app admin can view as someone else")
    try:
        target_id = UUID(person_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad person id") from None
    with db.transaction() as conn:
        person = db.fetch_one(
            conn, "select * from people where id = %s and active and role <> 'admin'", [target_id]
        )
        if person is None:
            raise HTTPException(status_code=404, detail="That person isn't active any more")
        stores = db.fetch_all(conn, "select store_id from store_members where person_id = %s", [target_id])
    if method.upper() not in READ_ONLY_METHODS:
        raise HTTPException(
            status_code=403,
            detail=f"You're viewing as {person['name']}: read-only. Switch back to yourself to make changes.",
        )
    return CurrentUser(
        id=person["id"], email=person["email"], name=person["name"], role=person["role"],
        store_ids=[s["store_id"] for s in stores], viewed_by=admin,
    )


def current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_dev_email: str | None = Header(default=None),
    x_view_as: str | None = Header(default=None),
) -> CurrentUser:
    user = _signed_in_user(authorization, x_dev_email)
    if x_view_as:
        return _view_as(user, x_view_as, request.method)
    return user


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
