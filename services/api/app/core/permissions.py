"""Who may do what: one table for every role. The web app has the same table (apps/web/src/lib/access.ts).

    see_all_stores   sees every store and the owner's screens (review, reports, books, inventory, people, settings)
    make_changes     may save anything at all (worksheets, approvals, books, vendors, people, settings, exports)
    manage_owners    may add, change or remove owners and co-owners

Route guards then narrow it down: e.g. approving needs see_all_stores AND make_changes (owner_only + the gate).
"""

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({"see_all_stores", "make_changes", "manage_owners"}),
    "admin": frozenset({"see_all_stores", "make_changes", "manage_owners"}),   # app support (ADMIN_EMAILS)
    "coowner": frozenset({"see_all_stores"}),                                  # sees everything, changes nothing
    "manager": frozenset({"make_changes"}),                                    # own stores' worksheets
    "employee": frozenset({"make_changes"}),                                   # own stores' worksheets
}


def can(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
