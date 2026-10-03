"""Sign-in token checks: both Supabase signing styles, and bad tokens."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app.core import auth
from app.core.config import get_settings


def _claims(**extra):
    return {"email": "emp@example.com", "sub": "user-1", "aud": "authenticated", "exp": int(time.time()) + 600} | extra


@pytest.fixture(autouse=True)
def fresh_settings(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    yield
    get_settings.cache_clear()


def test_key_pair_token_is_accepted(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(_claims(), private, algorithm="ES256")

    class FakeJwks:
        def get_signing_key_from_jwt(self, _):
            return type("K", (), {"key": private.public_key()})()

    monkeypatch.setattr(auth, "_jwks_client", lambda: FakeJwks())
    assert auth._email_from_token(token) == ("emp@example.com", "user-1")


def test_shared_secret_token_is_accepted(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "s3cret-s3cret-s3cret-s3cret-s3cret!")
    get_settings.cache_clear()
    token = jwt.encode(_claims(), "s3cret-s3cret-s3cret-s3cret-s3cret!", algorithm="HS256")
    assert auth._email_from_token(token)[0] == "emp@example.com"


def test_forged_or_expired_tokens_are_refused(monkeypatch):
    forged = jwt.encode(_claims(), "not-the-secret-not-the-secret-123!", algorithm="HS256")
    with pytest.raises(HTTPException) as err:
        auth._email_from_token(forged)  # no secret configured -> refused
    assert err.value.status_code == 401

    monkeypatch.setenv("SUPABASE_JWT_SECRET", "s3cret-s3cret-s3cret-s3cret-s3cret!")
    get_settings.cache_clear()
    expired = jwt.encode(_claims(exp=int(time.time()) - 10), "s3cret-s3cret-s3cret-s3cret-s3cret!", algorithm="HS256")
    with pytest.raises(HTTPException):
        auth._email_from_token(expired)
