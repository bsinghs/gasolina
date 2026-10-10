"""Gasolina API. Start with:  uvicorn app.main:app --reload

Each feature lives in app/modules/<feature>/ with its own router. To add a feature, add a module
and one `include_router` line below. Interactive API docs: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import db
from app.core.auth import bootstrap_admins, bootstrap_owner
from app.core.auth import CurrentUser, owner_only
from app.core.config import get_settings
from app.core.json import exact
from app.core.release import app_version, record_release, release_log, running
from app.modules.admin.router import router as admin_router
from app.modules.exports.router import router as exports_router
from app.modules.me.router import router as me_router
from app.modules.people.router import router as people_router
from app.modules.reports.router import router as reports_router
from app.modules.settings.router import router as settings_router
from app.modules.stores.router import router as stores_router
from app.modules.summaries.router import router as summaries_router
from app.modules.books.router import router as books_router
from app.modules.vendors.router import router as vendors_router
from app.modules.inventory.router import router as inventory_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    bootstrap_owner()
    bootstrap_admins()
    record_release()
    yield
    db.close_pool()


app = FastAPI(title="Gasolina API", version=app_version(), lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for router in [me_router, stores_router, people_router, reports_router, exports_router, settings_router, admin_router, summaries_router, books_router, vendors_router, inventory_router]:
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    """Called every 5 minutes by Cloud Scheduler. Touching the database keeps Supabase's
    free project from pausing in quiet weeks, and shows if the database is unreachable."""
    with db.transaction() as conn:
        db.fetch_one(conn, "select 1 as ok")
    return {"ok": True, **running()}


@app.get("/api/releases")
def releases(_: CurrentUser = Depends(owner_only)):
    """The release log: each time an API started with a new version or commit (test and production)."""
    return exact(release_log())
