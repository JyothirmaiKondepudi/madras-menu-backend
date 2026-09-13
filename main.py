from fastapi import FastAPI
from routes.users import router as users_router
from routes.projects import router as projects_router
from routes.invoices import router as invoice_router
from routes.service import router as service_router

# Schema is now managed by Alembic migrations (see alembic/versions/), not
# Base.metadata.create_all() — run `alembic upgrade head` after changing a
# model, instead of relying on app startup to create/adjust tables.

app = FastAPI()
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(invoice_router)
app.include_router(service_router)

@app.get("/")
def health_status():
    return {"status": "ok"}
