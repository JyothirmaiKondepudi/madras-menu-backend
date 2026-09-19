import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from routes.users import router as users_router
from routes.projects import router as projects_router
from routes.invoices import router as invoice_router
from routes.service import router as service_router
from routes.menu_items import router as menu_items_router
from routes.tax_categories import router as tax_categories_router
from routes.item_relationships import router as item_relationships_router
from embeddings.routes import router as embeddings_router
from auth.routes import router as auth_router
from hierarchy.mutations import HierarchyError

# Schema is now managed by Alembic migrations (see alembic/versions/), not
# Base.metadata.create_all() — run `alembic upgrade head` after changing a
# model, instead of relying on app startup to create/adjust tables.

logger = logging.getLogger("uvicorn.error")

app = FastAPI()
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(invoice_router)
app.include_router(service_router)
app.include_router(menu_items_router)
app.include_router(tax_categories_router)
app.include_router(item_relationships_router)
app.include_router(embeddings_router)
app.include_router(auth_router)


# --- Global error handling --------------------------------------------------
# One handler per error type here, instead of a try/except in every route —
# applies to every route automatically, including ones added later. Registered
# here rather than per-router so there's exactly one place that decides how
# each kind of failure looks to a client.

@app.exception_handler(HierarchyError)
def handle_hierarchy_error(request: Request, exc: HierarchyError):
    # a rejected mutation (cycle, self-parent, already exists, etc.) — not a
    # bug, the caller asked for something the tree's rules don't allow
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
def handle_integrity_error(request: Request, exc: IntegrityError):
    # a real constraint violation (unique, FK, not-null) surfaced by Postgres
    # itself — e.g. deleting a menu item still referenced by item_relationships
    logger.warning("IntegrityError on %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse(status_code=409, content={"detail": str(exc.orig)})


@app.exception_handler(OperationalError)
def handle_operational_error(request: Request, exc: OperationalError):
    # the database itself is unreachable/down/connection dropped — not the
    # caller's fault, nothing to fix on their end
    logger.error("OperationalError on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is currently unavailable. Please try again shortly."},
    )


@app.exception_handler(ConnectionError)
def handle_ollama_connection_error(request: Request, exc: ConnectionError):
    # Ollama itself isn't reachable — raised as a plain builtins.ConnectionError
    # by langchain-ollama/the ollama client, confirmed by actually triggering
    # it (Ollama wasn't installed on this machine at the time this was
    # written), not guessed at. Distinct from OperationalError (Postgres
    # down) — this is specifically the embedding/classification model being
    # unavailable, not the database.
    logger.error("ConnectionError (likely Ollama unreachable) on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The embedding/LLM service (Ollama) is currently unavailable. Please try again shortly."},
    )


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception):
    # last resort — anything not covered above. Logged in full server-side,
    # never shown to the client, so nothing internal ever leaks in a response
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


@app.get("/")
def health_status():
    return {"status": "ok"}
