"""Cross-org isolation (ticket B1): a vendor must never read, change, delete
or attach things to another org's data. Every case returns 404, the same as
a missing id, so other orgs' ids can't be probed."""
import pytest
from sqlalchemy.orm import sessionmaker

from auth.security import hash_password
from models import Organization, User

PASSWORD = "correct-horse-battery-staple"


def _subproject_body(project_id):
    return {
        "subprojectName": "Mehendi",
        "projectAssociatedTo": project_id,
        "cuisine": ["South Indian"],
        "religion": "Hindu",
        "subprojectDate": "2026-11-13T19:00:00",
        "guestCount": 80,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "mehendi",
    }


def _project_body(vendor_id, name="Org A Project"):
    return {
        "projectName": name,
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": vendor_id,
    }


def _invoice_body(project_id, user_id, **overrides):
    body = {
        "invoiceStatus": "Generated",
        "totalAmount": 1000.0,
        "depositPercentage": 25,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }
    body.update(overrides)
    return body


@pytest.fixture()
def org_a(client, test_user, test_project, vendor_auth_headers):
    """Org A's data, owned by the default test vendor."""
    subproject = client.post(
        "/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers
    ).json()
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], subprojectId=subproject["subprojectId"]),
        headers=vendor_auth_headers,
    ).json()
    return {
        "project": test_project["projectId"],
        "subproject": subproject["subprojectId"],
        "invoice": invoice["invoiceId"],
        "user": test_user["userId"],
    }


@pytest.fixture()
def vendor_b(client, engine):
    """A vendor in a second org, with their own auth headers."""
    db = sessionmaker(bind=engine)()
    org = Organization(orgName="Org B Caterers", orgEmail="org.b@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    vendor = User(
        fullName="Vendor B",
        userEmail="vendor.b@example.com",
        userPhoneNumber="5559998888",
        preferredContact="email",
        userRole="vendor",
        userOrg=org.orgId,
        passwordHash=hash_password(PASSWORD),
    )
    db.add(vendor)
    db.commit()
    user_id = str(vendor.userId)
    db.close()

    token = client.post("/auth/login", json={"email": "vendor.b@example.com", "password": PASSWORD}).json()
    return {"userId": user_id, "headers": {"Authorization": f"Bearer {token['access_token']}"}}


# --- Vendor B acting on Org A's records by id ------------------------------

@pytest.mark.parametrize("method, path, body", [
    ("get", "/projects/{project}", None),
    ("patch", "/projects/{project}", {"projectName": "Taken over"}),
    ("delete", "/projects/{project}", None),
    ("post", "/projects/{project}/users/{vendor_b}", None),
    ("patch", "/projects/{project}/final-invoice/{invoice}", None),
    ("get", "/subprojects/{subproject}", None),
    ("patch", "/subprojects/{subproject}", {"guestCount": 1}),
    ("delete", "/subprojects/{subproject}", None),
    ("get", "/invoices/{invoice}", None),
    ("patch", "/invoices/{invoice}", {"invoiceStatus": "Paid"}),
    ("delete", "/invoices/{invoice}", None),
    ("patch", "/invoices/{invoice}/accept", None),
    ("patch", "/invoices/{invoice}/reject", None),
    ("get", "/invoices/{invoice}/pdf", None),
    ("get", "/billing-history/invoices/{invoice}", None),
    ("get", "/users/{user}", None),
    ("patch", "/users/{user}", {"fullName": "Taken over"}),
    ("delete", "/users/{user}", None),
])
def test_other_org_vendor_gets_404(client, org_a, vendor_b, method, path, body):
    url = path.format(vendor_b=vendor_b["userId"], **org_a)
    kwargs = {"headers": vendor_b["headers"]}
    if body is not None:
        kwargs["json"] = body
    resp = getattr(client, method)(url, **kwargs)
    assert resp.status_code == 404, resp.text


def test_other_org_writes_leave_data_untouched(client, org_a, vendor_b, vendor_auth_headers):
    b = vendor_b["headers"]
    client.patch(f"/projects/{org_a['project']}", json={"projectName": "Taken over"}, headers=b)
    client.delete(f"/invoices/{org_a['invoice']}", headers=b)
    client.delete(f"/subprojects/{org_a['subproject']}", headers=b)
    client.delete(f"/projects/{org_a['project']}", headers=b)
    client.delete(f"/users/{org_a['user']}", headers=b)

    project = client.get(f"/projects/{org_a['project']}", headers=vendor_auth_headers)
    assert project.status_code == 200
    assert project.json()["projectName"] != "Taken over"
    assert client.get(f"/subprojects/{org_a['subproject']}", headers=vendor_auth_headers).status_code == 200
    assert client.get(f"/invoices/{org_a['invoice']}", headers=vendor_auth_headers).status_code == 200
    assert client.get(f"/users/{org_a['user']}", headers=vendor_auth_headers).status_code == 200


# --- Vendor B creating things under Org A's parents -------------------------

def test_other_org_cannot_add_subproject_to_project(client, org_a, vendor_b):
    resp = client.post("/subprojects", json=_subproject_body(org_a["project"]), headers=vendor_b["headers"])
    assert resp.status_code == 404


def test_other_org_cannot_add_invoice_to_project(client, org_a, vendor_b):
    resp = client.post(
        "/invoices", json=_invoice_body(org_a["project"], vendor_b["userId"]), headers=vendor_b["headers"]
    )
    assert resp.status_code == 404


def test_other_org_cannot_record_payment_on_invoice(client, org_a, vendor_b):
    resp = client.post(
        "/billing-history/payments", json={"invoiceId": org_a["invoice"], "amount": 5000}, headers=vendor_b["headers"]
    )
    assert resp.status_code == 404


# --- Org A pointing its own records at Org B's users ------------------------

def test_cannot_add_other_org_user_to_project(client, org_a, vendor_b, vendor_auth_headers):
    resp = client.post(f"/projects/{org_a['project']}/users/{vendor_b['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_cannot_create_project_with_other_org_vendor(client, vendor_b, vendor_auth_headers):
    resp = client.post("/projects", json=_project_body(vendor_b["userId"]), headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_cannot_set_other_org_vendor_on_project(client, org_a, vendor_b, vendor_auth_headers):
    resp = client.patch(
        f"/projects/{org_a['project']}", json={"vendorOnProject": vendor_b["userId"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_cannot_bill_other_org_user(client, org_a, vendor_b, vendor_auth_headers):
    resp = client.post(
        "/invoices", json=_invoice_body(org_a["project"], vendor_b["userId"]), headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_cannot_reassign_invoice_to_other_org_user(client, org_a, vendor_b, vendor_auth_headers):
    resp = client.patch(
        f"/invoices/{org_a['invoice']}", json={"invoiceAssignedTo": vendor_b["userId"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 404


# --- An invoice's subproject must belong to the invoice's own project -------

def test_invoice_subproject_must_belong_to_its_project(client, org_a, test_user, vendor_auth_headers):
    other_project = client.post(
        "/projects", json=_project_body(test_user["userId"], name="Another Org A Project"), headers=vendor_auth_headers
    ).json()
    other_subproject = client.post(
        "/subprojects", json=_subproject_body(other_project["projectId"]), headers=vendor_auth_headers
    ).json()

    create = client.post(
        "/invoices",
        json=_invoice_body(org_a["project"], org_a["user"], subprojectId=other_subproject["subprojectId"]),
        headers=vendor_auth_headers,
    )
    update = client.patch(
        f"/invoices/{org_a['invoice']}",
        json={"subprojectId": other_subproject["subprojectId"]},
        headers=vendor_auth_headers,
    )
    assert create.status_code == 404
    assert update.status_code == 404
