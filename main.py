import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
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
from config import get_settings

# fail at startup, listing every missing or invalid setting (see config.py)
settings = get_settings()

# Schema is managed by Alembic migrations — run `alembic upgrade head` after changing a model.

logger = logging.getLogger("uvicorn.error")

app = FastAPI()
app.include_router(org_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(invoice_router)
app.include_router(subproject_router)
app.include_router(menu_items_router)
app.include_router(tax_categories_router)
app.include_router(item_relationships_router)
app.include_router(embeddings_router)
app.include_router(auth_router)
app.include_router(notifications_router)
app.include_router(billing_history_router)
app.include_router(billing_info_router)

# --- API activity logging ---------------------------------------------------
# One api_logs row per request, including 401/422/404s and unhandled 500s.


def _client_ip(request: Request) -> str | None:
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:  # e.g. "testclient"
        return None


@app.middleware("http")
async def log_api_activity(request: Request, call_next):
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
            route=getattr(request.scope.get("route"), "path", None),
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


@app.get("/")
def health_status():
    return {"status": "ok"}
