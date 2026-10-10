"""The permissions table (no database)."""

from app.core.auth import CurrentUser
from app.core.permissions import ROLE_PERMISSIONS, can


def test_every_role_is_in_the_table():
    assert set(ROLE_PERMISSIONS) == {"owner", "admin", "coowner", "manager", "employee"}


def test_coowner_sees_everything_and_changes_nothing():
    assert can("coowner", "see_all_stores") and not can("coowner", "make_changes") and not can("coowner", "manage_owners")


def test_owner_admin_staff():
    assert all(can(r, p) for r in ("owner", "admin") for p in ("see_all_stores", "make_changes", "manage_owners"))
    assert can("employee", "make_changes") and not can("employee", "see_all_stores")
    assert not can("nobody", "make_changes")


def test_current_user_flags():
    co = CurrentUser(id=None, email="c", name="C", role="coowner")
    assert co.is_owner and not co.can_change and not co.is_full_owner
    owner = CurrentUser(id=None, email="o", name="O", role="owner")
    assert owner.can_change and owner.is_full_owner
    viewed = CurrentUser(id=None, email="o", name="O", role="owner", viewed_by=owner)   # admin's View as
    assert not viewed.can_change
