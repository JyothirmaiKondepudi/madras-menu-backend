import os

# Must be set before importing anything that reads DATABASE_URL at import
# time (database.py does, via os.environ.get at module load).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/madras_menu_test"
)

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import models  # noqa: F401 — registers every ORM class on Base.metadata
from database import Base, get_db
from main import app

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    # menu_item_embeddings needs the pgvector extension — enabled on
    # madras_menu_local via the Docker init script at first container boot,
    # but never automatically on a separately-created test database. Without
    # this, Base.metadata.create_all() below fails with "type vector does
    # not exist" the first time a fresh test DB is used (hit for real: a
    # freshly-created madras_menu_test on this machine didn't have it).
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(autouse=True)
def clean_tables(engine):
    """Runs after every test — deletes all rows from every table this app
    owns, in FK-safe order, so tests never see another test's leftovers.
    Kept simple (delete-all, not per-test transactions) since this is a
    small, fully disposable database with real Postgres behavior."""
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client(engine):
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(client):
    resp = client.post("/users", json={
        "fullName": "Test User",
        "email": "test.user@example.com",
        "phoneNumber": "5550001111",
        "preferredContact": "email",
        "role": "client",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def test_project(client, test_user):
    resp = client.post("/projects", json={
        "projectName": "Test Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-01T18:00:00",
        "projectEndDate": "2026-11-01T23:00:00",
        "adminOnProject": test_user["userId"],
        "clientId": test_user["userId"],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def test_menu_item(client):
    resp = client.post("/menu-items", json={
        "name": "Test Dish",
        "course": "main",
        "vegNonveg": "veg",
        "priceWeight": "standard",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()
