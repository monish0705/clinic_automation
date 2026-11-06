import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn

from app.core.config import settings
from app.core.logging import logger
from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.workers.reminder_worker import run_reminder_cycle
from scripts.init_db import init_and_seed_db

# Routers
from app.api.routes import (
    health,
    authentication,
    appointments,
    doctors,
    patients,
    conversations,
    webhooks
)

scheduler = BackgroundScheduler(daemon=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: database verification, scheduler startup and teardown."""
    if settings.APP_ENV == "test" or os.environ.get("APP_ENV") == "test":
        yield
        return

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")

    # 1. Initialize & Seed DB tables if not present
    try:
        init_and_seed_db()
    except Exception as exc:
        logger.error(f"Error during database bootstrap: {exc}")

    # 2. Start Background Reminder Scheduler only in non-test mode
    if settings.APP_ENV != "test":
        try:
            scheduler.add_job(
                run_reminder_cycle,
                "interval",
                minutes=settings.REMINDER_INTERVAL_MINUTES,
                id="appointment_reminders",
                replace_existing=True
            )
            scheduler.start()
            logger.info(f"[SCHEDULER] Reminder worker scheduled every {settings.REMINDER_INTERVAL_MINUTES} minutes.")
        except Exception as exc:
            logger.error(f"[SCHEDULER] Could not start reminder scheduler: {exc}")

    yield

    # Teardown
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] Reminder scheduler stopped.")


def create_application() -> FastAPI:
    """Application factory configuring middleware, exception handlers, and routing."""
    app_env = os.environ.get("APP_ENV", "development")
    active_lifespan = lifespan if app_env != "test" else None

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production-grade AI WhatsApp automation platform for clinics and hospitals.",
        lifespan=active_lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Exception Handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred. Please contact clinic support."}
        )

    # Mount API Routers
    app.include_router(health.router)
    app.include_router(authentication.router)
    app.include_router(appointments.router)
    app.include_router(doctors.router)
    app.include_router(patients.router)
    app.include_router(conversations.router)
    app.include_router(webhooks.router)

    return app


app = create_application()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
