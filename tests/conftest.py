import os

# Must be set before importing anything that reads DATABASE_URL at import
# time (database.py does, via os.environ.get at module load).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/madras_menu_test"
)
# auth/security.py needs a SECRET_KEY to sign/verify JWTs — tests don't
# load .env.local (nothing in this app does; see database.py), so give it
# a fixed, obviously-fake default rather than letting every auth test fail
# with a None signing key when run outside a real dev environment.
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
# services/invoice_pdf.py writes real PDF files — point tests at a throwaway
# temp directory instead of the repo's real storage/invoices folder.
import tempfile
os.environ.setdefault("INVOICE_PDF_DIR", tempfile.mkdtemp(prefix="madras_test_invoices_"))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import models  # noqa: F401 — registers every ORM class on Base.metadata
import uuid
from database import Base, get_db
from main import app
from auth.permissions import PERMISSIONS, ROLE_PERMISSIONS

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

# Static reference data, not per-test state — seeded once for the whole
# session (see the engine fixture) and deliberately excluded from
# clean_tables' per-test TRUNCATE below, or every test after the first
# would run with zero permissions granted to any role.
_REFERENCE_TABLES = {"permissions", "role_permissions"}


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

    # Base.metadata.create_all() only builds the schema — it doesn't run
    # Alembic migrations, so the real migration's seed data (every
    # permission, all granted to "vendor") never runs here. Re-seed from the
    # same auth.permissions module the migration imports from, so the two
    # can't drift apart.
    with eng.begin() as conn:
        permission_ids = {}
        for name, description in PERMISSIONS:
            permission_id = uuid.uuid4()
            permission_ids[name] = permission_id
            conn.execute(
                text("INSERT INTO permissions (id, name, description) VALUES (:id, :name, :description)"),
                {"id": permission_id, "name": name, "description": description},
            )
        for role, permission_names in ROLE_PERMISSIONS.items():
            for name in permission_names:
                conn.execute(
                    text("INSERT INTO role_permissions (role, permission_id) VALUES (:role, :permission_id)"),
                    {"role": role, "permission_id": permission_ids[name]},
                )

    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(autouse=True)
def clean_tables(engine):
    """Runs after every test — wipes every table this app owns (except the
    static reference tables above), so tests never see another test's
    leftovers. TRUNCATE ... CASCADE, not a per-table DELETE in
    sorted_tables order — projects.final_invoice_id and
    invoices.project_associated_to form a real FK cycle between those two
    tables, and a test that actually sets finalInvoiceId (test_set_final_invoice)
    creates a genuine circular row reference that no single delete order can
    satisfy. CASCADE sidesteps the ordering question entirely."""
    yield
    table_names = ", ".join(
        table.name for table in Base.metadata.tables.values() if table.name not in _REFERENCE_TABLES
    )
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} CASCADE"))


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
def test_vendor_login(engine):
    """The one bootstrap vendor every other fixture/test authenticates as.
    Created directly against the DB, NOT via POST /users — that route is
    itself vendor-only now, so creating the very first vendor has to happen
    out-of-band, the same real bootstrapping step a production deployment
    of this app would need once (see auth plan)."""
    from sqlalchemy.orm import sessionmaker
    from models import User
    from auth.security import hash_password

    Session = sessionmaker(bind=engine)
    db = Session()
    vendor = User(
        fullName="Login Test Vendor",
        userEmail="login.vendor@example.com",
        userPhoneNumber="5550003333",
        preferredContact="email",
        userRole="vendor",
        passwordHash=hash_password("correct-horse-battery-staple"),
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    result = {
        "userId": str(vendor.userId),
        "fullName": vendor.fullName,
        "userEmail": vendor.userEmail,
        "userRole": vendor.userRole,
    }
    db.close()
    return result


@pytest.fixture()
def vendor_auth_headers(client, test_vendor_login):
    """Bearer headers for a vendor — the common case for tests that just
    need *some* authenticated, unrestricted caller and aren't themselves
    testing authorization scoping. Also what every other fixture below
    uses to create its own test data, now that POST /users/POST /projects/
    POST /menu-items etc. all require a vendor."""
    resp = client.post("/auth/login", json={
        "email": test_vendor_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def test_user(client, vendor_auth_headers):
    resp = client.post("/users", json={
        "fullName": "Test User",
        "email": "test.user@example.com",
        "phoneNumber": "5550001111",
        "preferredContact": "email",
        "role": "client",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def test_project(client, test_user, vendor_auth_headers):
    resp = client.post("/projects", json={
        "projectName": "Test Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-01T18:00:00",
        "projectEndDate": "2026-11-01T23:00:00",
        "vendorOnProject": test_user["userId"],
        "clientId": test_user["userId"],
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def test_client_login(client, vendor_auth_headers):
    """A client-role user with a real password set — for auth/project-
    authorization tests that need to actually log in, unlike the plain
    test_user fixture (which has no password and can't)."""
    resp = client.post("/users", json={
        "fullName": "Login Test Client",
        "email": "login.client@example.com",
        "phoneNumber": "5550002222",
        "preferredContact": "email",
        "role": "client",
        "password": "correct-horse-battery-staple",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def test_menu_item(client, vendor_auth_headers):
    resp = client.post("/menu-items", json={
        "name": "Test Dish",
        "course": "main",
        "vegNonveg": "veg",
        "priceWeight": "standard",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()
