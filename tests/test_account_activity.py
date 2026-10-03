from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from models import AccountActivity


def _activity_rows(engine, **filters):
    """No GET /account-activity route exists yet, so tests read the table
    directly — same as how conftest.py's test_vendor_login fixture opens
    its own Session against the shared test engine."""
    Session = sessionmaker(bind=engine)
    db = Session()
    query = select(AccountActivity)
    for column, value in filters.items():
        query = query.where(getattr(AccountActivity, column) == value)
    rows = db.execute(query.order_by(AccountActivity.occurredAt)).scalars().all()
    db.close()
    return rows


def _project_with_vendor_and_client(client, vendor_id, client_id, headers):
    project = client.post("/projects", json={
        "projectName": "Activity Test Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": vendor_id,
    }, headers=headers).json()
    if client_id is not None:
        client.post(f"/projects/{project['projectId']}/users/{client_id}", headers=headers)
    return project


def _subproject_body(project_id):
    return {
        "subprojectName": "Activity Test Subproject",
        "projectAssociatedTo": project_id,
        "cuisine": ["South Indian"],
        "religion": "Hindu",
        "subprojectDate": "2026-12-01T19:00:00",
        "guestCount": 50,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
        "minPricePerPerson": 40.0,
        "maxPricePerPerson": 60.0,
    }


def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_user_created_writes_activity(client, vendor_auth_headers, test_vendor_login, engine):
    resp = client.post("/users", json={
        "fullName": "Activity Test User",
        "email": "activity.user@example.com",
        "phoneNumber": "5551110000",
        "preferredContact": "email",
        "role": "client",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text

    rows = _activity_rows(engine, actorId=test_vendor_login["userId"], activityType="user_created")
    matching = [r for r in rows if "Activity Test User" in r.description]
    assert len(matching) == 1
    assert matching[0].projectId is None


def test_project_created_writes_activity(client, test_project, test_vendor_login, engine):
    rows = _activity_rows(engine, projectId=test_project["projectId"], activityType="project_created")
    assert len(rows) == 1
    assert rows[0].description == f'Project "{test_project["projectName"]}" was created'


def test_subproject_created_writes_activity(client, test_project, vendor_auth_headers, engine):
    resp = client.post("/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    subproject = resp.json()

    rows = _activity_rows(engine, subprojectId=subproject["subprojectId"], activityType="subproject_created")
    assert len(rows) == 1
    assert str(rows[0].projectId) == test_project["projectId"]


def test_invoice_generated_writes_activity(client, test_user, test_project, vendor_auth_headers, engine):
    resp = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "totalAmount": 250.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": test_user["userId"],
        "projectAssociatedTo": test_project["projectId"],
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text

    rows = _activity_rows(engine, projectId=test_project["projectId"], activityType="invoice_generated")
    assert len(rows) == 1
    assert "$250.00" in rows[0].description


def test_invoice_accepted_writes_activity_with_client_as_actor(
    client, test_vendor_login, test_client_login, vendor_auth_headers, engine
):
    project = _project_with_vendor_and_client(
        client, test_vendor_login["userId"], test_client_login["userId"], vendor_auth_headers
    )
    invoice = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": test_client_login["userId"],
        "projectAssociatedTo": project["projectId"],
    }, headers=vendor_auth_headers).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/accept", headers={"Authorization": f"Bearer {client_token}"}
    )
    assert resp.status_code == 200, resp.text

    rows = _activity_rows(engine, projectId=project["projectId"], activityType="invoice_accepted")
    assert len(rows) == 1
    assert str(rows[0].actorId) == test_client_login["userId"]


def test_invoice_declined_writes_no_activity(
    client, test_vendor_login, test_client_login, vendor_auth_headers, engine
):
    project = _project_with_vendor_and_client(
        client, test_vendor_login["userId"], test_client_login["userId"], vendor_auth_headers
    )
    invoice = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": test_client_login["userId"],
        "projectAssociatedTo": project["projectId"],
    }, headers=vendor_auth_headers).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/reject", headers={"Authorization": f"Bearer {client_token}"}
    )
    assert resp.status_code == 200, resp.text

    rows = _activity_rows(engine, projectId=project["projectId"])
    assert all(r.activityType != "invoice_declined" for r in rows)
    assert all(r.activityType != "invoice_rejected" for r in rows)


def test_project_assigned_writes_activity_once_not_twice(
    client, test_project, test_client_login, vendor_auth_headers, test_vendor_login, engine
):
    url = f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}"
    assert client.post(url, headers=vendor_auth_headers).status_code == 200
    # calling it again is a no-op — should NOT write a second row
    assert client.post(url, headers=vendor_auth_headers).status_code == 200

    rows = [
        r for r in _activity_rows(engine, projectId=test_project["projectId"], activityType="project_assigned")
        if test_client_login["fullName"] in r.description
    ]
    assert len(rows) == 1
    assert str(rows[0].actorId) == test_vendor_login["userId"]
    assert test_client_login["fullName"] in rows[0].description


def test_project_user_added_notifies_vendor_and_original_client(
    client, test_vendor_login, test_client_login, vendor_auth_headers
):
    original_client = client.post("/users", json={
        "fullName": "Original Client",
        "email": "original.client.activity@example.com",
        "phoneNumber": "5551110001",
        "preferredContact": "email",
        "role": "client",
        "password": "correct-horse-battery-staple",
    }, headers=vendor_auth_headers).json()

    project = _project_with_vendor_and_client(
        client, test_vendor_login["userId"], original_client["userId"], vendor_auth_headers
    )

    resp = client.post(
        f"/projects/{project['projectId']}/users/{test_client_login['userId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    vendor_unread = client.get("/notifications/unread", headers=vendor_auth_headers).json()
    assert any(
        n["type"] == "project_user_added" and test_client_login["fullName"] in n["message"]
        for n in vendor_unread
    )

    original_client_token = _login(client, original_client["userEmail"])
    original_client_unread = client.get(
        "/notifications/unread", headers={"Authorization": f"Bearer {original_client_token}"}
    ).json()
    assert any(
        n["type"] == "project_user_added" and "your project" in n["message"]
        for n in original_client_unread
    )


def test_project_user_added_skips_self_notification(
    client, test_vendor_login, test_client_login, vendor_auth_headers
):
    """Adding a client must notify the vendor, but must NOT send the client
    a notification about themselves."""
    project = _project_with_vendor_and_client(
        client, test_vendor_login["userId"], None, vendor_auth_headers
    )

    client_token = _login(client, test_client_login["userEmail"])
    client_auth = {"Authorization": f"Bearer {client_token}"}
    before = client.get("/notifications/unread", headers=client_auth).json()

    resp = client.post(
        f"/projects/{project['projectId']}/users/{test_client_login['userId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    after = client.get("/notifications/unread", headers=client_auth).json()
    assert len(after) == len(before)

    vendor_unread = client.get("/notifications/unread", headers=vendor_auth_headers).json()
    assert any(n["type"] == "project_user_added" for n in vendor_unread)


def test_deleting_project_cascades_activity_rows(client, test_project, vendor_auth_headers, engine):
    """Real bug caught earlier by this exact scenario: account_activity's
    FKs must cascade on delete, or removing a project it references fails
    with a 409 instead of succeeding."""
    resp = client.delete(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 204, resp.text

    rows = _activity_rows(engine, projectId=test_project["projectId"])
    assert rows == []
