"""What the menu engine (madras-menu-engine) relies on from this backend: login
tokens that carry the user's organization and role, and the event types the
engine has layouts for."""

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from auth.security import decode_access_token
from config import get_settings
from models.choices import EventType

PASSWORD = "correct-horse-battery-staple"
NEW_EVENTS = ["Sangeet", "Late-night Snacks", "Engagement", "Brunch"]


def _claims(token):
    s = get_settings()
    return jwt.decode(token, s.SECRET_KEY, algorithms=[s.JWT_ALGORITHM])


def _login(client, email):
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_a_vendor_login_token_carries_org_and_role(client, test_vendor_login):
    claims = _claims(_login(client, test_vendor_login["userEmail"]))
    assert claims["sub"] == test_vendor_login["userId"]
    assert claims["org"] == test_vendor_login["userOrg"]
    assert claims["role"] == "vendor"
    assert "exp" in claims


def test_a_client_login_token_carries_their_role(client, test_client_login):
    claims = _claims(_login(client, test_client_login["userEmail"]))
    assert claims["role"] == "client"
    assert claims["org"]


def test_the_backend_still_reads_only_the_user_id(client, test_vendor_login):
    token = _login(client, test_vendor_login["userEmail"])
    assert str(decode_access_token(token)) == test_vendor_login["userId"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["userId"] == test_vendor_login["userId"]


def test_the_event_list_has_the_engines_new_types():
    assert set(NEW_EVENTS) <= {e.value for e in EventType}


@pytest.mark.parametrize("event", NEW_EVENTS)
def test_a_subproject_can_be_one_of_the_new_events(client, test_project, vendor_auth_headers, event):
    body = {
        "subprojectName": f"{event} night", "projectAssociatedTo": test_project["projectId"],
        "subprojectDate": "2026-12-05T19:00:00", "guestCount": 180, "subprojectType": "Buffet",
        "subprojectVenue": "Hotel", "subprojectEvent": event,
    }
    resp = client.post("/subprojects", json=body, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["subprojectEvent"] == event


def test_the_database_accepts_the_new_events_and_still_refuses_unknown_ones(engine, test_project):
    """The rule on subproject_event and on the pricing tables' event_type."""
    with engine.connect() as conn:
        rules = dict(conn.execute(text(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conname IN ("
            "'subprojects_subproject_event_check', 'pricing_base_rates_event_check', "
            "'pricing_tier_additions_event_check', 'pricing_adjustments_event_check')"
        )).all())
    assert len(rules) == 4
    for name, definition in rules.items():
        for event in NEW_EVENTS:
            assert event in definition, (name, event)

    with pytest.raises(IntegrityError, match="subprojects_subproject_event_check"):
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE subprojects SET subproject_event = 'Pool Party' WHERE project_associated_to = :p"
            ), {"p": test_project["projectId"]})
            # nothing to update means no error: make sure there is a row
            conn.execute(text(
                "INSERT INTO subprojects (subproject_id, subproject_name, project_associated_to, subproject_date, "
                "guest_count, subproject_type, venue, subproject_event) VALUES (gen_random_uuid(), 'x', :p, now(), "
                "10, 'Buffet', 'Hotel', 'Pool Party')"
            ), {"p": test_project["projectId"]})
