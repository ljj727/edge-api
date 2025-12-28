"""
Edge Backend API - FastAPI Application

Main entry point for the FastAPI application.
Ported from C# ASP.NET Core backend.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api import router as api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db import models_registry  # noqa: F401 - Import to register models
from app.db.session import engine
from app.grpc import DetectorClient, set_grpc_client
from app.workers.event_retention import EventRetentionWorker
from app.workers.eventpush_worker import EventpushWorker
from app.workers.image_retention import ImageRetentionWorker
from app.workers.nats_subscriber import NatsEventSubscriber

settings = get_settings()

# Global instances
grpc_client: DetectorClient | None = None
nats_subscriber: NatsEventSubscriber | None = None
eventpush_worker: EventpushWorker | None = None
scheduler: AsyncIOScheduler | None = None


async def init_database() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def init_default_user() -> None:
    """Create default admin user if not exists."""
    from app.db.session import async_session_maker
    from app.services.user_service import UserService

    async with async_session_maker() as db:
        user_service = UserService(db)
        existing = await user_service.get_by_username("admin")
        if not existing:
            await user_service.create_user(
                user_id="admin",
                username="admin",
                password="admin",
                is_superuser=True,
            )
            logger.info("Default admin user created")


async def start_background_services() -> None:
    """Start background services."""
    global grpc_client, nats_subscriber, eventpush_worker, scheduler

    # Skip Core services if disabled (for frontend/backend only testing)
    if not settings.enable_core_services:
        logger.info("Core services disabled - skipping gRPC, NATS, and workers")
        return

    # Initialize gRPC client
    grpc_client = DetectorClient()
    try:
        await grpc_client.connect()
        set_grpc_client(grpc_client)  # Set global instance for other modules
    except Exception as e:
        logger.warning(f"gRPC connection failed (will retry): {e}")

    # Initialize eventpush worker
    eventpush_worker = EventpushWorker()
    asyncio.create_task(eventpush_worker.run())
    logger.info("Eventpush worker started")

    # Initialize NATS subscriber
    nats_subscriber = NatsEventSubscriber()

    # Register event handler to push to webhooks
    async def on_event(event: dict) -> None:
        if eventpush_worker:
            await eventpush_worker.enqueue(event)

    nats_subscriber.add_event_handler(on_event)

    try:
        asyncio.create_task(nats_subscriber.run())
        logger.info("NATS subscriber started")
    except Exception as e:
        logger.warning(f"NATS connection failed (will retry): {e}")

    # Initialize scheduler for periodic tasks
    scheduler = AsyncIOScheduler()

    # Event retention cleanup (daily at midnight)
    event_retention = EventRetentionWorker()
    scheduler.add_job(
        event_retention.run,
        "cron",
        hour=0,
        minute=0,
        id="event_retention",
    )

    # Image retention cleanup (every minute)
    image_retention = ImageRetentionWorker()
    scheduler.add_job(
        image_retention.run,
        "interval",
        minutes=1,
        id="image_retention",
    )

    scheduler.start()
    logger.info("Scheduler started")


async def stop_background_services() -> None:
    """Stop background services."""
    global grpc_client, nats_subscriber, eventpush_worker, scheduler

    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler stopped")

    if nats_subscriber:
        nats_subscriber.stop()
        logger.info("NATS subscriber stopped")

    if eventpush_worker:
        await eventpush_worker.stop()
        logger.info("Eventpush worker stopped")

    if grpc_client:
        await grpc_client.disconnect()
        set_grpc_client(None)  # Clear global instance
        logger.info("gRPC client disconnected")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Edge Backend API...")

    # Ensure data directory exists
    data_path = Path(settings.data_save_folder)
    data_path.mkdir(parents=True, exist_ok=True)

    await init_database()
    await init_default_user()
    await start_background_services()

    logger.info(f"Edge Backend API started on port {settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down Edge Backend API...")
    await stop_background_services()
    logger.info("Edge Backend API stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Edge Backend API - Detection Event Management System",
    lifespan=lifespan,
    docs_url="/swagger" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"Code": 500, "Message": str(exc)},
    )


# OPTIONS handler for CORS preflight
@app.options("/{path:path}")
async def options_handler(path: str) -> Response:
    """Handle OPTIONS requests for CORS preflight."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, skip-auth, Range",
        },
    )


# Include API router
app.include_router(api_router)


# Static file serving for HLS streaming
static_path = Path(settings.static_file_path)
if static_path.exists():
    app.mount(
        "/video",
        StaticFiles(directory=str(static_path)),
        name="video",
    )


# SPA fallback (serve index.html for non-API routes)
@app.get("/{path:path}", response_model=None)
async def spa_fallback(path: str):
    """Serve SPA index.html for non-API routes."""
    if path.startswith("api/") or path.startswith("video/"):
        return JSONResponse(
            status_code=404,
            content={"Code": 404, "Message": "Not found"},
        )

    index_path = Path("wwwroot/index.html")
    if index_path.exists():
        return FileResponse(index_path)

    return JSONResponse(
        status_code=404,
        content={"Code": 404, "Message": "Not found"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers,
    )
