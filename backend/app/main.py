"""
Main FastAPI Application for Website Archive Submitter & Automated Backup Repository.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.db.database import init_db, get_db_context
from backend.app.queue.queue_manager import QueueManager
from backend.app.queue.worker_pool import worker_pool
from backend.app.scheduler.scheduler_service import scheduler_service
from backend.app.routes.api import router as api_router
from backend.app.routes.auth import router as auth_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("archiver_app")

# Base paths
FRONTEND_DIR = settings.BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle hooks."""
    logger.info("Initializing database...")
    init_db()

    # Crash recovery on boot: reclaim any expired/orphaned leases from previous runs
    with get_db_context() as db:
        reclaimed = QueueManager.reclaim_expired_leases(db, lease_timeout_seconds=0)
        if reclaimed > 0:
            logger.info(f"Crash recovery: reclaimed {reclaimed} in-progress queue items.")

    # Start worker pool
    logger.info("Starting background submission worker pool...")
    worker_pool.start()

    # Start recurring scheduler
    logger.info("Starting background scheduler...")
    scheduler_service.start()

    yield

    # Graceful shutdown
    logger.info("Shutting down worker pool and scheduler...")
    worker_pool.stop()
    scheduler_service.stop()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS middleware for open accessibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and template configuration
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include API routes
app.include_router(api_router)
app.include_router(auth_router)


@app.get("/")
def render_dashboard(request: Request):
    """Render the primary interactive web dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "worker_running": worker_pool.is_running(),
        "worker_paused": worker_pool.is_paused(),
    }
