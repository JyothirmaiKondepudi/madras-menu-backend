import logging

from fastapi import APIRouter, FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
# not Python's built-in TimeoutError: raised when no pooled connection frees up in time
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.concurrency import run_in_threadpool
import time
import uuid
import ipaddress
from fastapi.middleware.cors import CORSMiddleware

from routes.users import router as users_router
from routes.projects import router as projects_router
from routes.invoices import router as invoice_router
from routes.subproject import router as subproject_router
from routes.menu_items import router as menu_items_router
from routes.tax_categories import router as tax_categories_router
from routes.item_relationships import router as item_relationships_router
from embeddings.routes import router as embeddings_router
from auth.routes import router as auth_router
from routes.notifications import router as notifications_router
from routes.billing_history import router as billing_history_router
from routes.billing_info import router as billing_info_router
from routes.organizations import router as org_router
from services.api_log_activity import record_api_log
from hierarchy.mutations import HierarchyError
from database import engine, get_db
from auth.viewer import reset_current_request, set_current_request
from config import get_settings

# fail at startup, listing every missing or invalid setting (see config.py)
settings = get_settings()

_UNLOGGED_PATHS = {"/", "/db/health"}

# Schema is managed by Alembic migrations — run `alembic upgrade head` after changing a model.

logger = logging.getLogger("uvicorn.error")

app = FastAPI()

# Every API route lives under /api/v1 (BE-27); a breaking change would go
# under /api/v2 alongside it. The health checks below stay at the root,
# where Docker and Cloud Run probe them.
API_PREFIX = "/api/v1"
api = APIRouter(prefix=API_PREFIX)
for router in (
    org_router,
    users_router,
    projects_router,
    invoice_router,
    subproject_router,
    menu_items_router,
    tax_categories_router,
    item_relationships_router,
    embeddings_router,
    auth_router,
    notifications_router,
    billing_history_router,
    billing_info_router,
):
    api.include_router(router)
app.include_router(api)

# --- API activity logging ---------------------------------------------------
# One api_logs row per request, including 401/422/404s and unhandled 500s.


def _client_ip(request: Request) -> str | None:
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:  # e.g. "testclient"
        return None


def _route_template(request: Request) -> str | None:
    """The matched route's path template, e.g. /api/v1/users/{user_id}.
    The route only knows its path inside its router, so add the prefix back:
    otherwise /api/v1 and a future /api/v2 would log the same template."""
    route_path = getattr(request.scope.get("route"), "path", None)
    if route_path is not None and request.url.path.startswith(API_PREFIX + "/"):
        return API_PREFIX + route_path
    return route_path


@app.middleware("http")
async def remember_request(request: Request, call_next):
    # lets response schemas see who's asking (auth/viewer.py)
    token = set_current_request(request)
    try:
        return await call_next(request)
    finally:
        reset_current_request(token)


@app.middleware("http")
async def log_api_activity(request: Request, call_next):
    if request.url.path in _UNLOGGED_PATHS:
        return await call_next(request)
    start = time.perf_counter()
    request_id = uuid.uuid4()
    status_code, error = 500, None
    try:
        response = await call_next(request)  # runs auth, validation, the route
        status_code = response.status_code
        response.headers["X-Request-ID"] = str(request_id)
        return response
    except Exception as exc:
        # Return the 500 here instead of re-raising: Starlette's own 500 is
        # built outside every middleware, so it would miss the CORS headers
        # and the browser would report a CORS error instead of the real one.
        error = repr(exc)
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers={"X-Request-ID": str(request_id)},
        )
    finally:
        await run_in_threadpool(
            record_api_log,  # own session, wrapped in try/except so it never breaks the request
            requestId=request_id,
            orgId=getattr(request.state, "org_id", None),
            method=request.method,
            queryParams=dict(request.query_params) or None,
            userAgent=request.headers.get("user-agent"),
            path=request.url.path,
            route=_route_template(request),
            statusCode=status_code,
            duration_ms=int((time.perf_counter() - start) * 1000),
            userId=getattr(request.state, "user_id", None),
            ipAddress=_client_ip(request),
            error=error,
        )


CORS_ORIGINS = settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)


# --- Global error handling --------------------------------------------------
# One handler per error type, registered here so every route (including future
# ones) gets consistent error responses without a try/except per route.


@app.exception_handler(HierarchyError)
def handle_hierarchy_error(request: Request, exc: HierarchyError):
    # rejected mutation (cycle, self-parent, etc.) — not a bug, an invalid request
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# Postgres error code -> (status, message). The raw error names tables,
# constraints and sometimes values, so it only goes to the server log.
_INTEGRITY_ERRORS = {
    "23505": (409, "A record with these details already exists."),  # unique
    "23503": (409, "This record is linked to other records."),  # foreign key
    "23502": (422, "A required field is missing."),  # not null
    "23514": (422, "One of the values isn't allowed."),  # check
}


@app.exception_handler(IntegrityError)
def handle_integrity_error(request: Request, exc: IntegrityError):
    # constraint violation (unique, FK, not-null, check) surfaced by Postgres
    logger.warning(
        "IntegrityError on %s %s: %s", request.method, request.url.path, exc.orig
    )
    status_code, detail = _INTEGRITY_ERRORS.get(
        getattr(exc.orig, "pgcode", None),
        (409, "The request conflicts with existing data."),
    )
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(OperationalError)
def handle_operational_error(request: Request, exc: OperationalError):
    # database unreachable/down — not the caller's fault
    logger.error("OperationalError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database is currently unavailable. Please try again shortly."
        },
    )


@app.exception_handler(PoolTimeoutError)
def handle_pool_timeout(request: Request, exc: PoolTimeoutError):
    # The database is up, but every pooled connection stayed busy for
    # DB_POOL_TIMEOUT seconds: a capacity problem, so log the pool's state
    # (pool too small, or a request holding its connection too long?)
    logger.error(
        "Connection pool exhausted on %s %s: %s",
        request.method,
        request.url.path,
        engine.pool.status(),
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "The server is busy. Please try again in a moment."},
        headers={"Retry-After": "5"},
    )


@app.exception_handler(ConnectionError)
def handle_ollama_connection_error(request: Request, exc: ConnectionError):
    # Ollama (embedding/LLM service) unreachable, raised as a plain ConnectionError
    logger.error(
        "ConnectionError (likely Ollama unreachable) on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The embedding/LLM service (Ollama) is currently unavailable. Please try again shortly."
        },
    )


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception):
    # last resort — logged in full server-side, never leaked to the client
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "An unexpected error occurred."}
    )


@app.get("/db/health")
def db_health_status(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@app.get("/")
def health_status():

    return {"status": "ok"}
