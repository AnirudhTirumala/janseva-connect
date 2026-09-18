import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import Base, engine
from app.core.rate_limit import limiter
from app.core.schema_check import verify_schema_is_current
from app.utils.audit import log_api_action
from app.models import (  # noqa: F401 - registers models
    user, member, scheme, application, certificate, certificate_request, audit_event,
    certificate_type, weekly_activity, internal_message, issue,
)

from app.routers import auth, users, members, schemes, applications, application_documents, certificates, ai_assistant, dashboard, notifications, messages, audit, locations, weekly_activities, issues

logger = logging.getLogger("panchayat.startup")

# --- Startup security checks -------------------------------------------------
# These fail loudly (refuse to start) rather than silently running insecurely,
# since a misconfigured production deployment is worse than one that won't boot.
if settings.is_production:
    startup_errors = []
    if not settings.secret_key_is_configured or len(settings.SECRET_KEY) < 32:
        startup_errors.append("SECRET_KEY must be explicitly configured and at least 32 characters long")
    if settings.DATABASE_URL.startswith("sqlite"):
        startup_errors.append("DATABASE_URL must point to managed PostgreSQL or MySQL, not SQLite")
    if not settings.STORAGE_PATH.strip():
        startup_errors.append("STORAGE_PATH must point to a mounted persistent volume")
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        startup_errors.append("SMTP_HOST, SMTP_USER, and SMTP_PASSWORD must be configured for OTP delivery")
    if (
        not settings.cors_origins_list
        or any(not origin.startswith("https://") for origin in settings.cors_origins_list)
        or "*" in settings.cors_origins_list
    ):
        startup_errors.append("CORS_ORIGINS must contain only explicit HTTPS frontend origins")
    if not settings.allowed_hosts_list or "*" in settings.allowed_hosts_list:
        startup_errors.append("ALLOWED_HOSTS must contain explicit API hostnames")

    if startup_errors:
        logger.critical(
            "Refusing insecure production startup: %s", "; ".join(startup_errors)
        )
        sys.exit(1)
    try:
        Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.critical("Persistent STORAGE_PATH is not writable: %s", exc)
        sys.exit(1)

# Creates tables on startup if they don't exist yet.
# For a real production rollout you'd swap this for Alembic migrations,
# but for this capstone's scope, create_all keeps setup simple and reliable.
Base.metadata.create_all(bind=engine)

# create_all adds missing TABLES but never a missing COLUMN on an existing
# table, so a database from an older release keeps its old shape and every
# query touching a new column 500s. Name the gap instead of letting it
# surface as "Something went wrong on our side" on the login screen.
schema_gaps = verify_schema_is_current(engine, fail_fast=settings.is_production)
if schema_gaps and settings.is_production:
    sys.exit(1)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for JanSeva Connect, a Smart Community Management Platform for Andhra Pradesh",
    version="1.0.0",
    # Hide interactive API docs in production - they're a convenience for
    # development/grading, not something a public government platform
    # should expose by default (it reveals the full schema/endpoint map).
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.state.limiter = limiter

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)


@app.middleware("http")
async def catch_unhandled_errors(request: Request, call_next):
    """Turn an unhandled exception into a 500 *inside* the CORS middleware.

    Registration order matters here. Starlette runs the last-added middleware
    outermost, and FastAPI's @app.exception_handler(Exception) is served by
    ServerErrorMiddleware, which sits outside everything - so the response it
    builds never passes back through CORSMiddleware and carries no
    Access-Control-Allow-Origin header. A browser on a different origin (the
    frontend on Vercel, the API on Render) then blocks the response entirely
    and the user sees an opaque "Network Error" instead of the message below.

    This middleware is added BEFORE CORSMiddleware, so it ends up inside it
    and its response gets the CORS headers on the way out. The
    exception_handler below stays as a backstop for anything raised further
    out than this.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on our side. Please try again, or contact the office if it keeps happening."},
        )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never return a stack trace or ORM error text to a client.

    An unhandled error would otherwise surface the raw exception (table
    names, column values, connection strings) in the response body. The
    detail belongs in the server log; the caller gets a generic 500.
    """
    logger.exception("Unhandled error escaped the middleware stack on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our side. Please try again, or contact the office if it keeps happening."},
    )


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a moment and try again."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Adds standard defensive headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.middleware("http")
async def audit_state_changes(request: Request, call_next):
    """Capture server-side mutations, including rejected approval attempts."""
    response = await call_next(request)
    if (
        not settings.TESTING
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api/")
        and not request.url.path.startswith("/api/audit/")
    ):
        # log_api_action opens its own synchronous SQLAlchemy session. Calling
        # it directly from this async middleware would block the event loop -
        # and therefore every other in-flight request - for the duration of
        # the audit INSERT on every single write the platform handles.
        await run_in_threadpool(
            log_api_action,
            request.method,
            request.url.path,
            response.status_code,
            request.headers.get("authorization"),
        )
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(members.router)
app.include_router(schemes.router)
app.include_router(applications.router)
app.include_router(application_documents.router)
app.include_router(certificates.router)
app.include_router(ai_assistant.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(messages.router)
app.include_router(audit.router)
app.include_router(locations.router)
app.include_router(weekly_activities.router)
app.include_router(issues.router)


@app.get("/")
def root():
    return {
        "message": "Smart Community Management Platform API",
        "docs": "/docs" if not settings.is_production else None,
        "status": "running",
    }


@app.get("/api/health")
def health_check():
    """Liveness probe that also proves the database is reachable.

    A health check that only returns a constant will happily report "ok"
    while every real request fails on a dropped database connection, which
    is precisely when a platform host needs to know to restart or page.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check failed: database is unreachable")
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
