import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes import health
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.infrastructure.database import create_engine, create_sessionmaker
from app.infrastructure.redis import create_redis
from app.websocket import lobby

logger = logging.getLogger("huntme")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.app_debug)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.settings = settings
        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.redis = create_redis(settings)
        logger.info("startup", extra={"env": settings.app_env})
        try:
            yield
        finally:
            await app.state.redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="HuntMe API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production_like else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production_like else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router)
    app.include_router(lobby.router)
    return app


def get_app() -> FastAPI:  # uvicorn --factory app.main:get_app
    return create_app()
