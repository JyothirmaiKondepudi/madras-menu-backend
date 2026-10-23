"""Health checks: GET / only says the process is up (liveness), the DB
check says whether the database is reachable (readiness/monitoring)."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import get_db
from main import app

DB_HEALTH_PATH = "/db/health"
# the health checks stay at the root, outside /api/v1 where the test
# client's base URL points, so requests use the full URL
LIVENESS_URL = "http://testserver/"
DB_HEALTH_URL = "http://testserver" + DB_HEALTH_PATH


def _override_get_db_with_unreachable_database():
    # nothing listens on port 1, so connecting fails straight away with a
    # real OperationalError instead of waiting for a timeout
    dead_engine = create_engine("postgresql://postgres:postgres@localhost:1/nowhere")
    DeadSession = sessionmaker(bind=dead_engine)

    def override_get_db():
        db = DeadSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db


def test_liveness_check_is_ok(client):
    resp = client.get(LIVENESS_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_liveness_check_does_not_touch_the_database(client):
    # a database outage must not fail liveness, or the platform would
    # restart every container when only the database is down
    _override_get_db_with_unreachable_database()
    resp = client.get(LIVENESS_URL)
    assert resp.status_code == 200


def test_db_health_check_is_ok_when_database_is_up(client):
    resp = client.get(DB_HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_db_health_check_returns_503_when_database_is_down(client):
    _override_get_db_with_unreachable_database()
    resp = client.get(DB_HEALTH_URL)
    assert resp.status_code == 503
    # the raw driver error (host, port, credentials) must not reach the caller
    assert "localhost" not in resp.text


def test_health_checks_are_not_logged(client, engine):
    # probes run every few seconds; logging them would flood api_logs
    assert client.get(LIVENESS_URL).status_code == 200
    assert client.get(DB_HEALTH_URL).status_code == 200
    with engine.connect() as conn:
        logged = conn.execute(
            text("SELECT path FROM api_logs WHERE path IN ('/', :db_path)"),
            {"db_path": DB_HEALTH_PATH},
        ).scalars().all()
    assert logged == []
