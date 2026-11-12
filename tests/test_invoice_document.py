"""BE-04: the invoice as a document: numbers, line items, totals, snapshots."""
import re

import pytest
from sqlalchemy.orm import sessionmaker

from auth.security import hash_password
from models import Organization, User

PASSWORD = "correct-horse-battery-staple"


def _service(client, headers, **overrides):
    body = {"name": "Bartender", "price": "45", "pricingUnit": "hour"} | overrides
    return client.post("/rate-card", json=body, headers=headers).json()


def _equipment(client, headers, **overrides):
    return client.post("/equipment", json={"name": "Chafing dish", "amount": "25"} | overrides,
                       headers=headers).json()


def _invoice(client, project, user, headers, **body):
    payload = {
        "depositPercentage": 50,
        "invoiceAssignedTo": user["userId"],
        "projectAssociatedTo": project["projectId"],
    } | body
    return client.post("/invoices", json=payload, headers=headers)


@pytest.fixture()
def other_org_vendor(client, engine):
    db = sessionmaker(bind=engine)()
    org = Organization(orgName="Other Caterers", orgEmail="other@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    vendor = User(fullName="Other Vendor", userEmail="other.vendor@example.com", userRole="vendor",
                  userOrg=org.orgId, passwordHash=hash_password(PASSWORD))
    db.add(vendor)
    db.commit()
    vendor_id = str(vendor.userId)
    db.close()
    token = client.post("/auth/login", json={"email": "other.vendor@example.com", "password": PASSWORD}).json()
    return {"userId": vendor_id, "headers": {"Authorization": f"Bearer {token['access_token']}"}}


# --- line items and totals -------------------------------------------------------


def test_line_items_from_the_catalog_and_custom(client, test_user, test_project, vendor_auth_headers):
    bartender = _service(client, vendor_auth_headers)
    dish = _equipment(client, vendor_auth_headers)
    resp = _invoice(client, test_project, test_user, vendor_auth_headers, lineItems=[
        {"kind": "service", "sourceId": bartender["id"], "quantity": 4},
        {"kind": "equipment", "sourceId": dish["id"], "quantity": 10},
        {"kind": "custom", "name": "Delivery", "quantity": 1, "unitPrice": "150"},
    ], adjustmentPercentage=-10)
    assert resp.status_code == 200, resp.text
    inv = resp.json()

    lines = [(l["position"], l["kind"], l["name"], l["unitPrice"], l["lineTotal"]) for l in inv["lineItems"]]
    assert lines == [
        (0, "service", "Bartender", 45.0, 180.0),
        (1, "equipment", "Chafing dish", 25.0, 250.0),
        (2, "custom", "Delivery", 150.0, 150.0),
    ]
    assert inv["lineItems"][0]["pricingUnit"] == "hour"
    assert inv["subtotalAmount"] == 580.0
    assert inv["adjustmentPercentage"] == -10.0
    assert inv["totalAmount"] == 522.0      # 580 less 10%
    assert inv["invoiceAmount"] == 261.0    # 50% deposit
    assert inv["currency"] == "USD"


def test_a_catalog_line_can_override_name_and_price(client, test_user, test_project, vendor_auth_headers):
    bartender = _service(client, vendor_auth_headers)
    inv = _invoice(client, test_project, test_user, vendor_auth_headers, lineItems=[
        {"kind": "service", "sourceId": bartender["id"], "name": "Head bartender", "unitPrice": "60", "quantity": 2},
    ]).json()
    [line] = inv["lineItems"]
    assert (line["name"], line["unitPrice"], line["sourceId"]) == ("Head bartender", 60.0, bartender["id"])


def test_editing_the_catalog_later_leaves_invoices_alone(client, test_user, test_project, vendor_auth_headers):
    bartender = _service(client, vendor_auth_headers)
    inv = _invoice(client, test_project, test_user, vendor_auth_headers,
                   lineItems=[{"kind": "service", "sourceId": bartender["id"], "quantity": 1}]).json()
    client.patch(f"/rate-card/{bartender['id']}", json={"name": "Mixologist", "price": "99"}, headers=vendor_auth_headers)
    client.delete(f"/rate-card/{bartender['id']}", headers=vendor_auth_headers)

    [line] = client.get(f"/invoices/{inv['invoiceId']}", headers=vendor_auth_headers).json()["lineItems"]
    assert (line["name"], line["unitPrice"]) == ("Bartender", 45.0)


@pytest.mark.parametrize("body, reason", [
    ({}, "neither lines nor total"),
    ({"totalAmount": 100, "lineItems": [{"kind": "custom", "name": "x", "quantity": 1, "unitPrice": "1"}]}, "both"),
    ({"totalAmount": 100, "adjustmentPercentage": 5}, "adjustment without lines"),
    ({"lineItems": []}, "empty list"),
    ({"lineItems": [{"kind": "custom", "quantity": 1, "unitPrice": "5"}]}, "custom without name"),
    ({"lineItems": [{"kind": "custom", "name": "x", "quantity": 0, "unitPrice": "5"}]}, "zero quantity"),
    ({"lineItems": [{"kind": "custom", "name": "x", "quantity": 1, "unitPrice": "5"}], "adjustmentPercentage": -100}, "total of zero"),
    ({"totalAmount": 100, "currency": "usd"}, "lower-case currency"),
])
def test_invalid_invoices_are_rejected(client, test_user, test_project, vendor_auth_headers, body, reason):
    resp = _invoice(client, test_project, test_user, vendor_auth_headers, **body)
    assert resp.status_code == 422, (reason, resp.text)


def test_another_orgs_catalog_item_cant_be_used(client, test_user, test_project, vendor_auth_headers, other_org_vendor):
    theirs = _service(client, other_org_vendor["headers"])
    resp = _invoice(client, test_project, test_user, vendor_auth_headers,
                    lineItems=[{"kind": "service", "sourceId": theirs["id"], "quantity": 1}])
    assert resp.status_code == 422
    assert "catalog" in resp.json()["detail"]


def test_an_invoice_with_just_a_total_still_works(client, test_user, test_project, vendor_auth_headers):
    inv = _invoice(client, test_project, test_user, vendor_auth_headers, totalAmount=1000).json()
    assert inv["totalAmount"] == 1000.0 and inv["invoiceAmount"] == 500.0
    assert inv["lineItems"] == [] and inv["subtotalAmount"] is None


# --- editing ----------------------------------------------------------------------


def test_replacing_line_items_recomputes_the_totals(client, test_user, test_project, vendor_auth_headers):
    inv = _invoice(client, test_project, test_user, vendor_auth_headers,
                   lineItems=[{"kind": "custom", "name": "Food", "quantity": 1, "unitPrice": "100"}]).json()
    resp = client.patch(f"/invoices/{inv['invoiceId']}", json={
        "lineItems": [{"kind": "custom", "name": "Food", "quantity": 2, "unitPrice": "100"},
                      {"kind": "custom", "name": "Cake", "quantity": 1, "unitPrice": "50"}],
        "adjustmentPercentage": 10,
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text

    saved = client.get(f"/invoices/{inv['invoiceId']}", headers=vendor_auth_headers).json()
    assert [l["name"] for l in saved["lineItems"]] == ["Food", "Cake"]
    assert (saved["subtotalAmount"], saved["totalAmount"], saved["invoiceAmount"]) == (250.0, 275.0, 137.5)


def test_total_cant_be_edited_directly_when_there_are_lines(client, test_user, test_project, vendor_auth_headers):
    inv = _invoice(client, test_project, test_user, vendor_auth_headers,
                   lineItems=[{"kind": "custom", "name": "Food", "quantity": 1, "unitPrice": "100"}]).json()
    resp = client.patch(f"/invoices/{inv['invoiceId']}", json={"totalAmount": 999}, headers=vendor_auth_headers)
    assert resp.status_code == 422
    assert "line items" in resp.json()["detail"]


@pytest.mark.parametrize("change", [
    {"lineItems": [{"kind": "custom", "name": "Food", "quantity": 1, "unitPrice": "1"}]},
    {"adjustmentPercentage": -50},
    {"currency": "EUR"},
])
def test_the_document_is_fixed_once_accepted(client, test_user, test_project, vendor_auth_headers, change):
    inv = _invoice(client, test_project, test_user, vendor_auth_headers,
                   lineItems=[{"kind": "custom", "name": "Food", "quantity": 1, "unitPrice": "100"}]).json()
    client.post(f"/invoices/{inv['invoiceId']}/accept", headers=vendor_auth_headers)
    resp = client.patch(f"/invoices/{inv['invoiceId']}", json=change, headers=vendor_auth_headers)
    assert resp.status_code == 409, resp.text


# --- numbers ------------------------------------------------------------------------


def test_invoice_numbers_count_up_per_organization(
    client, test_user, test_project, vendor_auth_headers, other_org_vendor
):
    first = _invoice(client, test_project, test_user, vendor_auth_headers, totalAmount=10).json()["invoiceNumber"]
    second = _invoice(client, test_project, test_user, vendor_auth_headers, totalAmount=10).json()["invoiceNumber"]
    year, n1 = re.fullmatch(r"INV-(\d{4})-(\d{4})", first).groups()
    assert second == f"INV-{year}-{int(n1) + 1:04d}"

    # a deleted invoice's number isn't handed out again
    client.delete(f"/invoices/{_invoice(client, test_project, test_user, vendor_auth_headers, totalAmount=10).json()['invoiceId']}",
                  headers=vendor_auth_headers)
    fourth = _invoice(client, test_project, test_user, vendor_auth_headers, totalAmount=10).json()["invoiceNumber"]
    assert fourth == f"INV-{year}-{int(n1) + 3:04d}"

    # another organization has its own sequence
    b = other_org_vendor
    project = client.post("/projects", json={
        "projectName": "B", "projectStatus": "Proposal", "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00", "vendorOnProject": b["userId"],
    }, headers=b["headers"]).json()
    client.post(f"/projects/{project['projectId']}/users/{b['userId']}", headers=b["headers"])
    theirs = client.post("/invoices", json={"totalAmount": 10, "depositPercentage": 100, "invoiceAssignedTo": b["userId"],
                                            "projectAssociatedTo": project["projectId"]}, headers=b["headers"]).json()
    assert theirs["invoiceNumber"] == f"INV-{year}-0001"


def test_simultaneous_invoices_get_different_numbers(engine, test_vendor_login):
    """The second waits for the first's counter row, then takes the next number."""
    import threading
    from uuid import UUID

    from sqlalchemy.orm import Session

    from services.invoice_document import next_invoice_number

    org_id = UUID(test_vendor_login["userOrg"])
    results = {}

    def second():
        with Session(engine) as db:
            results["second"] = next_invoice_number(org_id, db)
            db.commit()

    with Session(engine) as first:
        results["first"] = next_invoice_number(org_id, first)  # holds the counter row
        thread = threading.Thread(target=second)
        thread.start()
        thread.join(timeout=1)
        waited = thread.is_alive()
        first.commit()
    thread.join(timeout=10)

    assert waited
    n_first, n_second = (int(results[k].rsplit("-", 1)[1]) for k in ("first", "second"))
    assert n_second == n_first + 1


# --- snapshots ------------------------------------------------------------------------


def test_snapshots_follow_edits_until_the_client_accepts(
    client, test_user, test_project, test_vendor_login, vendor_auth_headers
):
    org_id = test_vendor_login["userOrg"]
    client.patch(f"/organizations/{org_id}", json={"orgAddress": "1 Old Rd"}, headers=vendor_auth_headers)
    inv = _invoice(client, test_project, test_user, vendor_auth_headers, totalAmount=100).json()
    full = client.get(f"/invoices/{inv['invoiceId']}", headers=vendor_auth_headers).json()
    assert full["businessSnapshot"]["address"] == "1 Old Rd"
    assert full["clientSnapshot"]["email"] == test_user["userEmail"]

    # still Assigned: an edit picks up the new address
    client.patch(f"/organizations/{org_id}", json={"orgAddress": "2 New Ave"}, headers=vendor_auth_headers)
    client.patch(f"/invoices/{inv['invoiceId']}", json={"deliverables": "Dinner for 100"}, headers=vendor_auth_headers)
    assert client.get(f"/invoices/{inv['invoiceId']}", headers=vendor_auth_headers).json()["businessSnapshot"]["address"] == "2 New Ave"

    # accepted: later profile changes don't reach it, even through an edit
    client.post(f"/invoices/{inv['invoiceId']}/accept", headers=vendor_auth_headers)
    client.patch(f"/organizations/{org_id}", json={"orgAddress": "3 Later Ln"}, headers=vendor_auth_headers)
    client.patch(f"/invoices/{inv['invoiceId']}", json={"dueDate": "2026-12-01T00:00:00Z"}, headers=vendor_auth_headers)
    assert client.get(f"/invoices/{inv['invoiceId']}", headers=vendor_auth_headers).json()["businessSnapshot"]["address"] == "2 New Ave"


# --- the PDF ------------------------------------------------------------------------------


def test_pdf_lists_the_document(client, engine, test_user, test_project, vendor_auth_headers):
    from uuid import UUID

    from sqlalchemy.orm import Session

    from models import Invoice
    from services.invoice_pdf import _invoice_lines

    inv = _invoice(client, test_project, test_user, vendor_auth_headers,
                   lineItems=[{"kind": "custom", "name": "Biryani tray", "quantity": 3, "unitPrice": "90"}],
                   adjustmentPercentage=-10, legalTerms="Payment due 7 days before the event.").json()
    with Session(engine) as db:
        invoice = db.get(Invoice, UUID(inv["invoiceId"]))
        text = "\n".join(line for _, line in _invoice_lines(invoice, db.get(User, invoice.invoiceAssignedTo)))
    for expected in (inv["invoiceNumber"], "Biryani tray: 3 x $90.00 = $270.00", "Subtotal: $270.00",
                     "Discount: 10%", "Event total: $243.00", "Payment due 7 days before the event."):
        assert expected in text, expected
