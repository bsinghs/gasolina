"""App-admin tools. Only exist on the TEST environment (APP_ENV=test).

On production these endpoints answer 404, so real data can never be wiped from the app.
"""

from fastapi import APIRouter, Depends

from app.core import db
from app.core.auth import CurrentUser, current_user
from app.core.config import get_settings
from app.core.errors import forbidden, not_found

router = APIRouter(prefix="/admin", tags=["admin"])

# Order matters: children first. daily_reports cascades to paid_outs, attachments, report_uploads.
RESET_STEPS = [
    ("history_rows", "delete from audit_log"),
    ("worksheets", "delete from daily_reports"),
    ("photos", "delete from attachments"),
    ("store_links", "delete from store_members"),
    ("people", "delete from people where role <> 'admin'"),
    ("stores", "delete from stores"),
]


@router.post("/reset-test-data")
def reset_test_data(user: CurrentUser = Depends(current_user)):
    """Wipe all test data except app admins and settings. TEST environment + admins only."""
    if not get_settings().is_test:
        raise not_found("Not found")
    if not user.is_admin:
        raise forbidden("Only the app admin can reset test data")
    removed = {}
    with db.transaction() as conn:
        for name, sql in RESET_STEPS:
            removed[name] = conn.execute(sql).rowcount
    return {"ok": True, "removed": removed}
