import os

# Must be set before database.py reads DATABASE_URL at import time.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/madras_menu_test"
)
# auth/security.py needs a SECRET_KEY to sign/verify JWTs; tests don't load .env.local
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
# services/invoice_pdf.py writes real PDF files — use a throwaway temp dir
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

# Seeded once per session (see engine fixture); excluded from clean_tables'
# per-test TRUNCATE, or every test after the first would have no permissions.
_REFERENCE_TABLES = {"permissions", "role_permissions"}


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    # menu_item_embeddings needs pgvector, which isn't auto-enabled on a fresh test DB
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(eng)

    # create_all() only builds the schema, it doesn't run the Alembic migration's seed
    # data — reseed from the same auth.permissions module the migration imports from
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
    """Wipes every table (except the reference tables above) after each test.
    Uses TRUNCATE ... CASCADE rather than per-table DELETE because projects
    and invoices have a circular FK (final_invoice_id / project_associated_to)
    that no single delete order can satisfy."""
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
    """The bootstrap vendor every other fixture/test authenticates as. Created
    directly in the DB, not via POST /users, since that route is vendor-only."""
    from sqlalchemy.orm import sessionmaker
    from models import Organization, User
    from auth.security import hash_password

    Session = sessionmaker(bind=engine)
    db = Session()
    # every user needs an org, so the org goes in first (same as scripts/seed_dev.py)
    org = Organization(orgName="Test Vendor Org", orgEmail="test.vendor.org@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    vendor = User(
        fullName="Login Test Vendor",
        userEmail="login.vendor@example.com",
        userPhoneNumber="5550003333",
        preferredContact="email",
        userRole="vendor",
        userOrg=org.orgId,
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
        "userOrg": str(vendor.userOrg),
    }
    db.close()
    return result


@pytest.fixture()
def platform_admin_headers(client, engine):
    """Bearer headers for a platform admin in its own (super) org. The only
    role allowed to create, list or delete organizations."""
    from sqlalchemy.orm import sessionmaker
    from models import Organization, User
    from auth.security import hash_password

    db = sessionmaker(bind=engine)()
    org = Organization(orgName="Platform Org", orgEmail="platform.org@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    db.add(User(
        fullName="Platform Admin",
        userEmail="platform.admin@example.com",
        userPhoneNumber="5550004444",
        preferredContact="email",
        userRole="platform_admin",
        userOrg=org.orgId,
        passwordHash=hash_password("correct-horse-battery-staple"),
    ))
    db.commit()
    db.close()

    resp = client.post("/auth/login", json={
        "email": "platform.admin@example.com",
        "password": "correct-horse-battery-staple",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def vendor_auth_headers(client, test_vendor_login):
    """Bearer headers for a vendor — the default authenticated caller for tests
    that aren't themselves testing authorization scoping."""
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
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    # clients are linked after creation, via user_projects
    resp = client.post(
        f"/projects/{resp.json()['projectId']}/users/{test_user['userId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def test_client_login(client, vendor_auth_headers):
    """A client-role user with a real password, for tests that need to log in
    (unlike test_user, which has no password)."""
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
