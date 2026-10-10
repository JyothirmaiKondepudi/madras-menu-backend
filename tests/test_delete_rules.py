"""C5: what can be deleted, what blocks it, and disabling users instead.

Deletes are refused with a 409 while something still points at the record:
subprojects block their project, invoices (even soft-deleted ones) block
their project, subproject and client, a vendor's projects block the vendor,
and users block their org. Users who can't be deleted are disabled instead."""
import uuid

from sqlalchemy import text

from tests.test_organizations import _create_org, _join_org

PASSWORD = "correct-horse-battery-staple"


def _subproject(client, project_id, headers):
    resp = client.post("/subprojects", json={
        "subprojectName": "Reception",
        "projectAssociatedTo": project_id,
        "cuisine": ["South Indian"],
        "religion": "Hindu",
        "subprojectDate": "2026-11-14T19:00:00",
        "guestCount": 100,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _invoice(client, project_id, user_id, headers, subproject_id=None):
    resp = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
        "subprojectId": subproject_id,
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _client_user(client, headers, email, password=None):
    body = {
        "fullName": "Another Client",
        "email": email,
        "phoneNumber": "5550005555",
        "preferredContact": "email",
        "role": "client",
    }
    if password:
        body["password"] = password
    resp = client.post("/users", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _login(client, email):
    return client.post("/auth/login", json={"email": email, "password": PASSWORD})


def _headers(login_resp):
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


# --- projects -------------------------------------------------------------

def test_project_with_subprojects_cannot_be_deleted(client, test_project, vendor_auth_headers):
    project_id = test_project["projectId"]
    _subproject(client, project_id, vendor_auth_headers)

    resp = client.delete(f"/projects/{project_id}", headers=vendor_auth_headers)
    assert resp.status_code == 409
    assert "1 sub projects" in resp.json()["detail"]
    assert client.get(f"/projects/{project_id}", headers=vendor_auth_headers).status_code == 200


def test_project_can_be_deleted_once_its_subprojects_are(client, test_project, vendor_auth_headers):
    project_id = test_project["projectId"]
    sub = _subproject(client, project_id, vendor_auth_headers)

    assert client.delete(f"/subprojects/{sub['subprojectId']}", headers=vendor_auth_headers).status_code == 204
    assert client.delete(f"/projects/{project_id}", headers=vendor_auth_headers).status_code == 204


def test_project_with_invoices_cannot_be_deleted(client, test_project, test_user, vendor_auth_headers):
    project_id = test_project["projectId"]
    _invoice(client, project_id, test_user["userId"], vendor_auth_headers)

    resp = client.delete(f"/projects/{project_id}", headers=vendor_auth_headers)
    assert resp.status_code == 409
    assert "invoices" in resp.json()["detail"]


# --- subprojects ----------------------------------------------------------

def test_subproject_with_invoices_cannot_be_deleted(client, test_project, test_user, vendor_auth_headers):
    sub = _subproject(client, test_project["projectId"], vendor_auth_headers)
    _invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers, sub["subprojectId"])

    resp = client.delete(f"/subprojects/{sub['subprojectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 409


def test_soft_deleted_invoice_still_blocks_its_subproject(client, test_project, test_user, vendor_auth_headers):
    sub = _subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, sub["subprojectId"]
    )
    assert client.delete(f"/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers).status_code == 204

    resp = client.delete(f"/subprojects/{sub['subprojectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 409, resp.text


# --- organizations --------------------------------------------------------

def test_org_with_users_cannot_be_deleted(client, engine, test_user, platform_admin_headers):
    org = _create_org(client, platform_admin_headers)
    _join_org(engine, test_user["userId"], org["orgId"])

    resp = client.delete(f"/organizations/{org['orgId']}", headers=platform_admin_headers)
    assert resp.status_code == 409
    assert "users" in resp.json()["detail"]


# --- users ----------------------------------------------------------------

def test_vendor_on_a_project_cannot_be_deleted(client, test_project, test_user, vendor_auth_headers):
    # test_project names test_user as its vendor
    resp = client.delete(f"/users/{test_user['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 409
    assert "disable" in resp.json()["detail"].lower()


def test_user_with_invoices_cannot_be_deleted(client, test_project, vendor_auth_headers):
    other = _client_user(client, vendor_auth_headers, "billed.client@example.com")
    _invoice(client, test_project["projectId"], other["userId"], vendor_auth_headers)

    resp = client.delete(f"/users/{other['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 409
    assert "invoices" in resp.json()["detail"]


def test_client_linked_to_a_project_can_be_deleted(client, test_project, vendor_auth_headers):
    # client links (user_projects) cascade; only vendor and invoice links block
    other = _client_user(client, vendor_auth_headers, "linked.client@example.com")
    linked = client.post(
        f"/projects/{test_project['projectId']}/users/{other['userId']}", headers=vendor_auth_headers
    )
    assert linked.status_code == 200, linked.text

    assert client.delete(f"/users/{other['userId']}", headers=vendor_auth_headers).status_code == 204
    assert client.get(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers).status_code == 200


def test_deleting_a_user_keeps_their_activity_history(client, engine, test_project, vendor_auth_headers):
    other = _client_user(client, vendor_auth_headers, "history.client@example.com")
    activity_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO account_activity (id, activity_type, description, actor_id, project_id, occurred_at) "
                "VALUES (:id, 'note', 'did something', :actor, :project, now())"
            ),
            {"id": activity_id, "actor": other["userId"], "project": test_project["projectId"]},
        )

    assert client.delete(f"/users/{other['userId']}", headers=vendor_auth_headers).status_code == 204
    with engine.connect() as conn:
        actor = conn.execute(
            text("SELECT actor_id FROM account_activity WHERE id = :id"), {"id": activity_id}
        ).one()
    assert actor.actor_id is None


# --- disabling users ------------------------------------------------------

def test_disabled_user_cannot_log_in(client, test_client_login, vendor_auth_headers):
    resp = client.post(f"/users/{test_client_login['userId']}/disable", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["userDisabled"] is True

    login = _login(client, test_client_login["userEmail"])
    assert login.status_code == 401
    # same answer as a wrong password, so it doesn't reveal the account state
    assert login.json()["detail"] == "Invalid email or password"


def test_disabled_users_existing_token_stops_working(client, test_client_login, vendor_auth_headers):
    client_headers = _headers(_login(client, test_client_login["userEmail"]))
    assert client.get("/projects", headers=client_headers).status_code == 200

    client.post(f"/users/{test_client_login['userId']}/disable", headers=vendor_auth_headers)
    assert client.get("/projects", headers=client_headers).status_code == 401


def test_enabling_restores_access(client, test_client_login, vendor_auth_headers):
    user_id = test_client_login["userId"]
    client.post(f"/users/{user_id}/disable", headers=vendor_auth_headers)

    resp = client.post(f"/users/{user_id}/enable", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["userDisabled"] is False
    assert _login(client, test_client_login["userEmail"]).status_code == 200


def test_cannot_disable_yourself(client, test_vendor_login, vendor_auth_headers):
    resp = client.post(f"/users/{test_vendor_login['userId']}/disable", headers=vendor_auth_headers)
    assert resp.status_code == 400
    assert client.get("/projects", headers=vendor_auth_headers).status_code == 200


def test_client_cannot_disable_users(client, test_client_login, test_user):
    client_headers = _headers(_login(client, test_client_login["userEmail"]))
    resp = client.post(f"/users/{test_user['userId']}/disable", headers=client_headers)
    assert resp.status_code == 403


def test_vendor_cannot_disable_user_in_another_org(client, engine, vendor_auth_headers, platform_admin_headers):
    with engine.connect() as conn:
        admin_id = conn.execute(
            text("SELECT user_id FROM user_data WHERE email = 'platform.admin@example.com'")
        ).scalar_one()
    resp = client.post(f"/users/{admin_id}/disable", headers=vendor_auth_headers)
    assert resp.status_code == 404
