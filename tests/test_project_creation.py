"""BE-06: POST /projects/full creates the client, project, subprojects and
first invoice together, or nothing at all."""
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from auth.security import hash_password
from models import Organization, User

URL = "/projects/full"


def _body(**overrides):
    body = {
        "client": {"email": "Priya.Shah@Example.com", "fullName": "Priya Shah", "phoneNumber": "8135550101"},
        "project": {
            "projectName": "Priya's Wedding",
            "projectStatus": "Proposal",
            "projectStartDate": "2026-12-01T17:00:00",
            "projectEndDate": "2026-12-05T23:00:00",
        },
        "subprojects": [
            {"subprojectName": "Mehendi", "subprojectDate": "2026-12-01T18:00:00", "guestCount": 80,
             "subprojectType": "Buffet", "subprojectVenue": "Home", "subprojectEvent": "Mehendi"},
            {"subprojectName": "Reception", "subprojectDate": "2026-12-05T19:00:00", "guestCount": 300,
             "subprojectType": "Plated", "subprojectVenue": "Hotel", "subprojectEvent": "Wedding Dinner"},
        ],
        "invoice": {
            "depositPercentage": 50,
            "subprojectIndex": 1,
            "lineItems": [{"kind": "custom", "name": "Dinner", "quantity": 300, "unitPrice": "40"}],
        },
    }
    for key, value in overrides.items():
        if value is None:
            body.pop(key)
        else:
            body[key] = value
    return body


def _count(engine, table, where="true", **params):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table} WHERE {where}"), params).scalar_one()


def _snapshot_counts(engine):
    return {t: _count(engine, t) for t in ("user_data", "projects", "subprojects", "invoices", "user_projects")}


def test_creates_everything_together(client, engine, vendor_auth_headers, test_vendor_login):
    resp = client.post(URL, json=_body(), headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    project = resp.json()

    # the client: created, lowercase email, linked to the project
    [linked] = project["clients"]
    assert linked["userEmail"] == "priya.shah@example.com"
    assert linked["userRole"] == "client"
    # the vendor defaults to whoever made the request
    assert project["vendorOnProject"] == test_vendor_login["userId"]

    # the subprojects, and the invoice on the second one (index 1)
    names = {s["subprojectName"]: s["subprojectId"] for s in project["subprojects"]}
    assert set(names) == {"Mehendi", "Reception"}
    [invoice] = project["invoices"]
    assert invoice["subprojectId"] == names["Reception"]
    assert invoice["invoiceAssignedTo"] == linked["userId"]
    assert (invoice["totalAmount"], invoice["invoiceAmount"]) == (12000.0, 6000.0)
    assert invoice["invoiceNumber"].startswith("INV-")

    # saved, not just returned
    saved = client.get(f"/projects/{project['projectId']}?include=subprojects,invoices",
                       headers=vendor_auth_headers).json()
    assert len(saved["subprojects"]) == 2 and len(saved["invoices"]) == 1
    pdf = client.get(f"/invoices/{invoice['invoiceId']}/pdf", headers=vendor_auth_headers)
    assert pdf.status_code == 200


def test_client_and_project_only(client, vendor_auth_headers):
    resp = client.post(URL, json=_body(subprojects=None, invoice=None), headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["subprojects"] == [] and resp.json()["invoices"] == []


def test_an_existing_client_is_reused_as_is(client, engine, vendor_auth_headers):
    first = client.post(URL, json=_body(subprojects=None, invoice=None), headers=vendor_auth_headers).json()
    # same person, different capitals and a different phone in the wizard
    again = _body(subprojects=None, invoice=None)
    again["client"] = {"email": "PRIYA.SHAH@example.com", "fullName": "P. Shah", "phoneNumber": "9999999999"}
    second = client.post(URL, json=again, headers=vendor_auth_headers).json()

    assert second["clients"][0]["userId"] == first["clients"][0]["userId"]
    # their saved details weren't changed by the wizard
    assert second["clients"][0]["fullName"] == "Priya Shah"
    assert second["clients"][0]["userPhoneNumber"] == "8135550101"
    assert _count(engine, "user_data", "email = :e", e="priya.shah@example.com") == 1


def test_email_from_another_organization_is_refused(client, engine, vendor_auth_headers):
    db = sessionmaker(bind=engine)()
    org = Organization(orgName="Elsewhere", orgEmail="else@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    db.add(User(fullName="Someone", userEmail="priya.shah@example.com", userRole="client", userOrg=org.orgId))
    db.commit()
    db.close()

    before = _snapshot_counts(engine)
    resp = client.post(URL, json=_body(), headers=vendor_auth_headers)
    assert resp.status_code == 409
    assert "another organization" in resp.json()["detail"]
    assert _snapshot_counts(engine) == before


def test_email_of_a_staff_account_is_refused(client, vendor_auth_headers, test_vendor_login):
    body = _body(subprojects=None, invoice=None)
    body["client"]["email"] = test_vendor_login["userEmail"]
    resp = client.post(URL, json=body, headers=vendor_auth_headers)
    assert resp.status_code == 409


def test_failure_in_the_last_step_saves_nothing(client, engine, vendor_auth_headers):
    """The heart of BE-06: the invoice is created last, so make it fail
    (a catalog item that doesn't exist) and check the client, project and
    subprojects created before it were rolled back too."""
    before = _snapshot_counts(engine)
    body = _body()
    body["invoice"]["lineItems"] = [{"kind": "service", "sourceId": str(uuid.uuid4()), "quantity": 1}]

    resp = client.post(URL, json=body, headers=vendor_auth_headers)
    assert resp.status_code == 422
    assert resp.json()["detail"].startswith("invoice:")
    assert _snapshot_counts(engine) == before
    assert _count(engine, "user_data", "email = :e", e="priya.shah@example.com") == 0


@pytest.mark.parametrize("index", [2, 5])
def test_invoice_pointing_past_the_subprojects_is_rejected(client, engine, vendor_auth_headers, index):
    before = _snapshot_counts(engine)
    body = _body()
    body["invoice"]["subprojectIndex"] = index
    resp = client.post(URL, json=body, headers=vendor_auth_headers)
    assert resp.status_code == 422
    assert _snapshot_counts(engine) == before


def test_project_level_invoice(client, vendor_auth_headers):
    body = _body()
    del body["invoice"]["subprojectIndex"]
    resp = client.post(URL, json=body, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoices"][0]["subprojectId"] is None


def test_vendor_from_another_organization_is_refused(client, engine, vendor_auth_headers):
    db = sessionmaker(bind=engine)()
    org = Organization(orgName="Elsewhere", orgEmail="else@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    other = User(fullName="Other Vendor", userEmail="v@else.com", userRole="vendor", userOrg=org.orgId,
                 passwordHash=hash_password("correct-horse-battery-staple"))
    db.add(other)
    db.commit()
    other_id = str(other.userId)
    db.close()

    body = _body()
    body["project"]["vendorOnProject"] = other_id
    assert client.post(URL, json=body, headers=vendor_auth_headers).status_code == 404


def test_clients_cant_use_it(client, test_client_login):
    token = client.post("/auth/login", json={
        "email": test_client_login["userEmail"], "password": "correct-horse-battery-staple",
    }).json()["access_token"]
    resp = client.post(URL, json=_body(), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
