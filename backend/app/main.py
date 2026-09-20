import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from app.api.errors import InvalidTransitionError, NotFoundError, ScanConflictError
from app.api.router import router
from app.core.clock import SystemClock
from app.core.config import get_settings
from app.persistence.database import get_engine, get_session_factory
from app.persistence.models import Base
from app.providers.errors import ProviderCredentialsError, ProviderError
from app.remediation.validators import InvalidIdentifierError
from app.services.app_context import AppContext, IdentityStatus
from app.services.demo_seeder import DemoSeeder
from app.services.provider_factory import build_provider
from app.services.scan_runner import ScanRunner
from app.services.settings_service import SettingsService


def _version() -> str:
    try:
        return version("cloudzombie-backend")
    except PackageNotFoundError:
        return "0.1.0"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        get_settings.cache_clear()
        get_session_factory.cache_clear()
        get_engine.cache_clear()
        environment = get_settings()
        logging.basicConfig(
            level=getattr(logging, environment.cloudzombie_log_level.upper(), logging.INFO)
        )
        engine = get_engine()
        if environment.database_url.startswith("sqlite"):
            expected = set(Base.metadata.tables)
            existing = set(inspect(engine).get_table_names())
            if not expected.issubset(existing):
                Base.metadata.create_all(engine)
        session_factory = get_session_factory()
        clock = SystemClock()
        with session_factory() as session:
            app_settings = SettingsService(session, environment).load()
            session.commit()
        provider = build_provider(environment, app_settings, clock)
        identity_status = IdentityStatus(mode=environment.cloudzombie_mode.value)
        context = AppContext(
            env=environment,
            clock=clock,
            session_factory=session_factory,
            provider=provider,
            identity_status=identity_status,
            version=_version(),
        )
        context.scan_runner = ScanRunner(context)
        application.state.context = context
        if environment.cloudzombie_mode.value == "demo" and environment.cloudzombie_demo_seed:
            DemoSeeder(session_factory, environment, clock).seed_if_empty()
        identity_status.refresh(provider, clock)
        yield

    application = FastAPI(
        title="CloudZombie",
        version=_version(),
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        lifespan=lifespan,
    )
    settings = get_settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    application.include_router(router)

    @application.exception_handler(ProviderCredentialsError)
    async def credentials_error(request: Request, exc: ProviderCredentialsError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "aws_credentials",
                    "message": str(exc),
                    "hint": (
                        "Configure an AWS profile or credential environment variables; "
                        "demo mode needs none."
                    ),
                }
            },
        )

    @application.exception_handler(ProviderError)
    async def provider_error(request: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": {"code": "aws_error", "message": str(exc)}},
        )

    @application.exception_handler(InvalidIdentifierError)
    async def identifier_error(request: Request, exc: InvalidIdentifierError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "invalid_identifier",
                    "message": str(exc),
                }
            },
        )

    def conflict(code: str, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": {"code": code, "message": str(exc)}},
        )

    @application.exception_handler(ScanConflictError)
    async def scan_conflict(request: Request, exc: ScanConflictError) -> JSONResponse:
        return conflict("scan_running", exc)

    @application.exception_handler(InvalidTransitionError)
    async def invalid_transition(request: Request, exc: InvalidTransitionError) -> JSONResponse:
        return conflict("invalid_transition", exc)

    @application.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": {"code": "not_found", "message": str(exc)}},
        )

    return application


app = create_app()
