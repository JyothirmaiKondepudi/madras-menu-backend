"""BE-22: role permissions are cached for PERMISSION_CACHE_SECONDS, so checks
don't hit the database, and a new grant still takes effect without a restart."""
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from auth import access

CLIENT = SimpleNamespace(userRole="client")


@pytest.fixture()
def fresh_cache():
    access.clear_permission_cache()
    yield
    access.clear_permission_cache()


@pytest.fixture()
def temporary_permission(engine):
    """A made-up permission, removed again afterwards: permissions are
    reference data that the per-test cleanup doesn't truncate."""
    name = f"test:{uuid.uuid4().hex[:8]}"
    permission_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO permissions (id, name, description) VALUES (:id, :n, 'test')"),
                     {"id": permission_id, "n": name})
    yield name, permission_id
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM role_permissions WHERE permission_id = :id"), {"id": permission_id})
        conn.execute(text("DELETE FROM permissions WHERE id = :id"), {"id": permission_id})


def _grant(engine, role, permission_id):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO role_permissions (role, permission_id) VALUES (:r, :id)"),
                     {"r": role, "id": permission_id})


def test_permission_checks_are_served_from_the_cache(engine, fresh_cache):
    statements = []

    def count(conn, cursor, statement, *args):
        statements.append(statement)

    with Session(engine) as db:
        access.user_has_permission(SimpleNamespace(userRole="vendor"), "project:create", db)
        event.listen(engine, "before_cursor_execute", count)
        try:
            for name in ("project:create", "invoice:view_all", "billing:void", "nope"):
                access.user_has_permission(SimpleNamespace(userRole="vendor"), name, db)
        finally:
            event.remove(engine, "before_cursor_execute", count)
    assert statements == []


def test_a_new_grant_takes_effect_once_the_cache_expires(engine, fresh_cache, temporary_permission, monkeypatch):
    name, permission_id = temporary_permission
    clock = [1000.0]
    monkeypatch.setattr(access.time, "monotonic", lambda: clock[0])

    with Session(engine) as db:
        assert not access.user_has_permission(CLIENT, name, db)
        _grant(engine, "client", permission_id)

        clock[0] += access.PERMISSION_CACHE_SECONDS - 1
        assert not access.user_has_permission(CLIENT, name, db)  # still cached

        clock[0] += 2  # past the window: reloaded, no restart needed
        assert access.user_has_permission(CLIENT, name, db)


def test_clearing_the_cache_applies_a_grant_immediately(engine, fresh_cache, temporary_permission):
    name, permission_id = temporary_permission
    with Session(engine) as db:
        assert not access.user_has_permission(CLIENT, name, db)
        _grant(engine, "client", permission_id)
        access.clear_permission_cache()
        assert access.user_has_permission(CLIENT, name, db)


def test_roles_are_cached_separately(engine, fresh_cache):
    with Session(engine) as db:
        assert access.user_has_permission(SimpleNamespace(userRole="vendor"), "project:create", db)
        assert not access.user_has_permission(CLIENT, "project:create", db)
