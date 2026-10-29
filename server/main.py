"""
RestoOS Production FastAPI Backend Server
High-throughput restaurant, bar, and two-tier inventory operating system.
Local LAN mesh deployment (0.0.0.0:8000) with zero external cloud dependencies.
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from .database import engine, Base, SessionLocal
from .models import Tenant
from .seed_data import seed_database

# Import Route Modules
from .routes.tables import router as tables_router
from .routes.orders import router as orders_router
from .routes.kot import router as kot_router
from .routes.billing import router as billing_router
from .routes.shifts import router as shifts_router
from .routes.inventory import router as inventory_router
from .routes.excise import router as excise_router
from .routes.owner import router as owner_router
from .routes.auth import router as auth_router
from .supabase_client import get_supabase_config

import sys

# Base directories
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    STATIC_DIR = BUNDLE_DIR / "static"
    if not STATIC_DIR.exists():
        STATIC_DIR = Path(sys.executable).parent / "static"
else:
    SERVER_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = SERVER_DIR.parent
    STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Server startup lifecycle:
    1. Ensures SQLite WAL tables exist with Foreign Keys.
    2. Auto-seeds database if virgin/empty.
    """
    print("=" * 60)
    print("Initializing RestoOS Server & Database Layer...")
    Base.metadata.create_all(bind=engine)

    # Check if DB has data; if empty, seed automatically
    db = SessionLocal()
    try:
        tenant_exists = db.query(Tenant).first()
        if not tenant_exists:
            print("Virgin database detected. Seeding initial RestoOS data...")
            seed_database()
        else:
            print("Existing RestoOS database detected and ready.")
    finally:
        db.close()

    print("RestoOS Backend is live on http://0.0.0.0:8000")
    print("=" * 60)
    yield
    print("RestoOS Backend shutting down.")


# Initialize FastAPI Application
app = FastAPI(
    title="RestoOS Restaurant Management API",
    description="High-Throughput Restaurant, Bar & Two-Tier Inventory Operating System (Indian Standard)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration: Enable all LAN mesh access (192.168.*, localhost, 127.0.0.1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 Routers under /api/v1
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(tables_router)
api_v1.include_router(orders_router)
api_v1.include_router(kot_router)
api_v1.include_router(billing_router)
api_v1.include_router(shifts_router)
api_v1.include_router(inventory_router)
api_v1.include_router(excise_router)
api_v1.include_router(owner_router)
api_v1.include_router(auth_router)

app.include_router(api_v1)


# Health & Cloud Configuration Endpoints
@app.get("/health", tags=["System Health"])
@app.get("/api/v1/health", tags=["System Health"])
def health_check():
    """System health check endpoint for LAN monitoring."""
    from .database import is_sqlite, DATABASE_URL
    return {
        "status": "healthy",
        "system": "RestoOS",
        "version": "1.0.0",
        "mode": "supabase_postgresql" if not is_sqlite else "local_lan_sqlite",
        "database": "postgresql" if not is_sqlite else "sqlite_wal_normal_sync",
        "supabase": get_supabase_config(),
    }


@app.get("/api/v1/config", tags=["System Health"])
def system_config():
    """Exposes cloud connectivity and Supabase runtime details."""
    from .database import is_sqlite
    return {
        "system": "RestoOS",
        "outlet": "Rasa Sahyadri · Koregaon Park, Pune",
        "version": "1.0.0",
        "is_cloud_postgres": not is_sqlite,
        "supabase": get_supabase_config(),
    }


# No-cache middleware for local LAN development & live updates
class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.endswith((".html", ".js", ".css")) or request.url.path in ("/", "/settings", "/menu", "/pos", "/owner", "/store", "/bar", "/shift"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheStaticMiddleware)

# SPA Client-Side Routes: direct URLs like /settings, /menu, /pos serve index.html
@app.api_route("/settings", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/menu", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/pos", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/store", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/bar", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/owner", methods=["GET", "HEAD"], include_in_schema=False)
@app.api_route("/shift", methods=["GET", "HEAD"], include_in_schema=False)
def serve_spa_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return JSONResponse(status_code=404, content={"detail": "index.html not found"})

# Mount Static Frontend Files (SPA) at root '/'
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    print(f"Warning: Static directory {STATIC_DIR} not found. Static file serving skipped.")


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
