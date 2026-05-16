from fastapi import FastAPI

from app.api.routes_admin import router as admin_router
from app.api.routes_ask import router as ask_router
from app.api.routes_auth import router as auth_router
from app.api.routes_documents import router as documents_router
from app.api.routes_evals import router as evals_router
from app.api.routes_health import router as health_router
from app.config import get_settings
from app.telemetry.logging import configure_logging
from app.telemetry.tracing import configure_tracing, instrument_fastapi


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(ask_router)
    app.include_router(evals_router)
    app.include_router(admin_router)
    app.include_router(health_router)
    instrument_fastapi(app, settings)
    return app


app = create_app()
