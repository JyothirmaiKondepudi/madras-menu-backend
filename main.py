import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.concurrency import run_in_threadpool
import time
import uuid
import ipaddress

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
        error = repr(exc)
        raise
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


# --- Global error handling --------------------------------------------------
# One handler per error type, registered here so every route (including future
# ones) gets consistent error responses without a try/except per route.


@app.exception_handler(HierarchyError)
def handle_hierarchy_error(request: Request, exc: HierarchyError):
    # rejected mutation (cycle, self-parent, etc.) — not a bug, an invalid request
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
def handle_integrity_error(request: Request, exc: IntegrityError):
    # constraint violation (unique, FK, not-null) surfaced by Postgres
    logger.warning(
        "IntegrityError on %s %s: %s", request.method, request.url.path, exc.orig
    )
    return JSONResponse(status_code=409, content={"detail": str(exc.orig)})


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
