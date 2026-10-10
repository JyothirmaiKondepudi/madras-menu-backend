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
        "subprojectEvent": "Mehendi",
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
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
        headers=vendor_auth_headers,
    ).json()
    invoice = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=subproject["subprojectId"],
        ),
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
    org = Organization(
        orgName="Org B Caterers", orgEmail="org.b@example.com", orgDisabled=False
    )
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

    token = client.post(
        "/auth/login", json={"email": "vendor.b@example.com", "password": PASSWORD}
    ).json()
    return {
        "userId": user_id,
        "headers": {"Authorization": f"Bearer {token['access_token']}"},
    }


@pytest.fixture()
def org_b(client, vendor_b):
    """Org B's data, created through the API by Vendor B."""
    b = vendor_b["headers"]
    project = client.post(
        "/projects",
        json=_project_body(vendor_b["userId"], name="Org B Project"),
        headers=b,
    ).json()
    subproject = client.post(
        "/subprojects", json=_subproject_body(project["projectId"]), headers=b
    ).json()
    invoice = client.post(
        "/invoices",
        json=_invoice_body(
            project["projectId"],
            vendor_b["userId"],
            subprojectId=subproject["subprojectId"],
        ),
        headers=b,
    ).json()
    return {
        "project": project["projectId"],
        "subproject": subproject["subprojectId"],
        "invoice": invoice["invoiceId"],
    }


# --- Vendor B acting on Org A's records by id ------------------------------


@pytest.mark.parametrize(
    "method, path, body",
    [
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
        ("get", "/invoices/projects/{project}", None),
        ("patch", "/invoices/{invoice}/accept", None),
        ("patch", "/invoices/{invoice}/reject", None),
        ("get", "/invoices/{invoice}/pdf", None),
        ("get", "/billing-history/invoices/{invoice}", None),
        ("get", "/billing-history/subprojects/{subproject}", None),
        ("get", "/billing-info/subprojects/{subproject}", None),
        ("get", "/users/{user}", None),
        ("get", "/projects/users/{user}", None),
        ("get", "/subprojects/projects/{project}", None),
        ("patch", "/users/{user}", {"fullName": "Taken over"}),
        ("delete", "/users/{user}", None),
    ],
)
def test_other_org_vendor_gets_404(client, org_a, vendor_b, method, path, body):
    url = path.format(vendor_b=vendor_b["userId"], **org_a)
    kwargs = {"headers": vendor_b["headers"]}
    if body is not None:
        kwargs["json"] = body
    resp = getattr(client, method)(url, **kwargs)
    assert resp.status_code == 404, resp.text


def test_org_b_cannot_access__org_a_invoice(client, vendor_b, org_a):
    response = client.get(
        f"/invoices/projects/{org_a['project']}", headers=vendor_b["headers"]
    )
    assert response.status_code == 404


def test_other_org_writes_leave_data_untouched(
    client, org_a, vendor_b, vendor_auth_headers
):
    b = vendor_b["headers"]
    client.patch(
        f"/projects/{org_a['project']}", json={"projectName": "Taken over"}, headers=b
    )
    client.delete(f"/invoices/{org_a['invoice']}", headers=b)
    client.delete(f"/subprojects/{org_a['subproject']}", headers=b)
    client.delete(f"/projects/{org_a['project']}", headers=b)
    client.delete(f"/users/{org_a['user']}", headers=b)

    project = client.get(f"/projects/{org_a['project']}", headers=vendor_auth_headers)
    assert project.status_code == 200
    assert project.json()["projectName"] != "Taken over"
    assert (
        client.get(
            f"/subprojects/{org_a['subproject']}", headers=vendor_auth_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/invoices/{org_a['invoice']}", headers=vendor_auth_headers
        ).status_code
        == 200
    )
    assert (
        client.get(f"/users/{org_a['user']}", headers=vendor_auth_headers).status_code
        == 200
    )


# --- Vendor B creating things under Org A's parents -------------------------


def test_other_org_cannot_add_subproject_to_project(client, org_a, vendor_b):
    resp = client.post(
        "/subprojects",
        json=_subproject_body(org_a["project"]),
        headers=vendor_b["headers"],
    )
    assert resp.status_code == 404


def test_other_org_cannot_add_invoice_to_project(client, org_a, vendor_b):
    resp = client.post(
        "/invoices",
        json=_invoice_body(org_a["project"], vendor_b["userId"]),
        headers=vendor_b["headers"],
    )
    assert resp.status_code == 404


def test_other_org_cannot_record_payment_on_invoice(client, org_a, vendor_b):
    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": org_a["invoice"], "amount": 50},
        headers=vendor_b["headers"],
    )
    assert resp.status_code == 404


def test_vendor_b_cannot_Access_org_a_subproject(client, org_a, vendor_b):
    response = client.get(
        f"/subprojects/projects/{org_a['project']}",
        headers=vendor_b["headers"],
    )
    assert response.status_code == 404


# --- Org A pointing its own records at Org B's users ------------------------


def test_cannot_add_other_org_user_to_project(
    client, org_a, vendor_b, vendor_auth_headers
):
    resp = client.post(
        f"/projects/{org_a['project']}/users/{vendor_b['userId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_cannot_create_project_with_other_org_vendor(
    client, vendor_b, vendor_auth_headers
):
    resp = client.post(
        "/projects", json=_project_body(vendor_b["userId"]), headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_cannot_set_other_org_vendor_on_project(
    client, org_a, vendor_b, vendor_auth_headers
):
    resp = client.patch(
        f"/projects/{org_a['project']}",
        json={"vendorOnProject": vendor_b["userId"]},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_cannot_bill_other_org_user(client, org_a, vendor_b, vendor_auth_headers):
    resp = client.post(
        "/invoices",
        json=_invoice_body(org_a["project"], vendor_b["userId"]),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_cannot_reassign_invoice_to_other_org_user(
    client, org_a, vendor_b, vendor_auth_headers
):
    resp = client.patch(
        f"/invoices/{org_a['invoice']}",
        json={"invoiceAssignedTo": vendor_b["userId"]},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


# --- An invoice's subproject must belong to the invoice's own project -------


def test_invoice_subproject_must_belong_to_its_project(
    client, org_a, test_user, vendor_auth_headers
):
    other_project = client.post(
        "/projects",
        json=_project_body(test_user["userId"], name="Another Org A Project"),
        headers=vendor_auth_headers,
    ).json()
    other_subproject = client.post(
        "/subprojects",
        json=_subproject_body(other_project["projectId"]),
        headers=vendor_auth_headers,
    ).json()

    create = client.post(
        "/invoices",
        json=_invoice_body(
            org_a["project"],
            org_a["user"],
            subprojectId=other_subproject["subprojectId"],
        ),
        headers=vendor_auth_headers,
    )
    update = client.patch(
        f"/invoices/{org_a['invoice']}",
        json={"subprojectId": other_subproject["subprojectId"]},
        headers=vendor_auth_headers,
    )
    assert create.status_code == 404
    assert update.status_code == 404


# --- List endpoints only return the caller's own org (ticket B2) ------------


def _org_b_payment(client, vendor_b):
    """Gives Org B a project, an invoice on one of its subprojects, and a payment."""
    b = vendor_b["headers"]
    project = client.post(
        "/projects",
        json=_project_body(vendor_b["userId"], name="Org B Project"),
        headers=b,
    ).json()
    subproject = client.post(
        "/subprojects", json=_subproject_body(project["projectId"]), headers=b
    ).json()
    invoice = client.post(
        "/invoices",
        json=_invoice_body(
            project["projectId"],
            vendor_b["userId"],
            subprojectId=subproject["subprojectId"],
        ),
        headers=b,
    ).json()
    client.patch(f"/invoices/{invoice['invoiceId']}/accept", headers=b)
    payment = client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 22.22},
        headers=b,
    )
    assert payment.status_code == 200, payment.text
    return {"subproject": subproject["subprojectId"], "payment": payment.json()["id"]}


def test_user_list_only_shows_own_org(client, org_a, vendor_b, vendor_auth_headers):
    ids = [
        u["userId"] for u in client.get("/users", headers=vendor_auth_headers).json()
    ]
    assert org_a["user"] in ids
    assert vendor_b["userId"] not in ids


def test_billing_history_list_only_shows_own_org(
    client, org_a, vendor_b, vendor_auth_headers
):
    client.patch(f"/invoices/{org_a['invoice']}/accept", headers=vendor_auth_headers)
    own = client.post(
        "/billing-history/payments",
        json={"invoiceId": org_a["invoice"], "amount": 11.11},
        headers=vendor_auth_headers,
    ).json()
    other = _org_b_payment(client, vendor_b)

    ids = [
        row["id"]
        for row in client.get("/billing-history", headers=vendor_auth_headers).json()
    ]
    assert ids == [own["id"]]  # just Org A's payment, exactly once
    assert other["payment"] not in ids


@pytest.mark.parametrize(
    "path, id_field, record",
    [
        ("/projects", "projectId", "project"),
        ("/subprojects", "subprojectId", "subproject"),
        ("/invoices", "invoiceId", "invoice"),
    ],
)
def test_list_only_shows_own_org(
    client, org_a, org_b, vendor_b, path, id_field, record
):
    resp = client.get(path, headers=vendor_b["headers"])
    assert resp.status_code == 200, resp.text

    ids = {item[id_field] for item in resp.json()}
    assert org_b[record] in ids, f"Vendor B can't see its own {record} in {path}"
    assert org_a[record] not in ids, f"Vendor B can see Org A's {record} in {path}"


def test_billing_info_list_only_shows_own_org(
    client, org_a, vendor_b, vendor_auth_headers
):
    client.patch(f"/invoices/{org_a['invoice']}/accept", headers=vendor_auth_headers)
    client.post(
        "/billing-history/payments",
        json={"invoiceId": org_a["invoice"], "amount": 11.11},
        headers=vendor_auth_headers,
    )
    other = _org_b_payment(client, vendor_b)

    ids = [
        row["subprojectId"]
        for row in client.get("/billing-info", headers=vendor_auth_headers).json()
    ]
    assert ids == [org_a["subproject"]]
    assert other["subproject"] not in ids
