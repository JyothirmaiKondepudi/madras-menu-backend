from fastapi import FastAPI
from routes.users import router as users_router
from database import Base, engine
import model  # noqa: F401 — importing this registers every ORM class on Base.metadata

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(users_router)

@app.get("/")
def health_status():
    return {"status": "ok"}
