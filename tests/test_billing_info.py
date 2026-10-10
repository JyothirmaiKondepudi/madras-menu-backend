import pytest


def _subproject_body(project_id):
    return {
        "subprojectName": "Billing Info Test Subproject",
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


def _create_subproject(client, project_id, headers):
    resp = client.post("/subprojects", json=_subproject_body(project_id), headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_invoice(client, project_id, user_id, headers, subproject_id, amount=100.0, accept=True):
    """Accepted by default, since only accepted invoices count toward billing_info."""
    resp = client.post(
        "/invoices",
        json={
            "invoiceStatus": "Generated",
            "totalAmount": amount,
            "depositPercentage": 100,
            "invoiceAssignedTo": user_id,
            "projectAssociatedTo": project_id,
            "subprojectId": subproject_id,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    if accept:
        resp = client.patch(f"/invoices/{resp.json()['invoiceId']}/accept", headers=headers)
        assert resp.status_code == 200, resp.text
    return resp.json()


def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_billing_info_requires_auth(client):
    assert client.get("/billing-info").status_code == 401


def test_get_billing_info_404_before_any_payment_recorded(client, test_project, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    resp = client.get(f"/billing-info/subprojects/{subproject['subprojectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_get_billing_info_for_nonexistent_subproject_404(client, vendor_auth_headers):
    resp = client.get(
        "/billing-info/subprojects/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_vendor_sees_all_billing_info(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 100},
        headers=vendor_auth_headers,
    )

    resp = client.get("/billing-info", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert any(i["subprojectId"] == subproject["subprojectId"] for i in resp.json())


def test_client_only_sees_billing_info_for_linked_projects(
    client, test_project, test_user, vendor_auth_headers, test_client_login
):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 100},
        headers=vendor_auth_headers,
    )

    token = _login(client, test_client_login["userEmail"])
    client_auth = {"Authorization": f"Bearer {token}"}

    assert client.get("/billing-info", headers=client_auth).json() == []
    resp = client.get(f"/billing-info/subprojects/{subproject['subprojectId']}", headers=client_auth)
    assert resp.status_code == 403

    client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )

    assert len(client.get("/billing-info", headers=client_auth).json()) == 1
    resp = client.get(f"/billing-info/subprojects/{subproject['subprojectId']}", headers=client_auth)
    assert resp.status_code == 200
    assert resp.json()["subprojectId"] == subproject["subprojectId"]


# --- billing_info stays in step with invoices (ticket C6) -------------------

def test_unaccepted_invoice_is_not_billed(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], amount=250.0, accept=False,
    )

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["status"] == "no_active_invoices"
    assert info["totalInvoiced"] == "0.00"
    assert info["balanceDue"] == "0.00"


def test_accepting_invoice_adds_it_to_billing_info(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], amount=250.0,
    )

    resp = client.get(f"/billing-info/subprojects/{subproject['subprojectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    info = resp.json()
    assert info["totalInvoiced"] == "250.00"
    assert info["totalPaid"] == "0.00"
    assert info["balanceDue"] == "250.00"
    assert info["status"] == "payment_pending"


def test_second_invoice_adds_to_total_invoiced(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    for amount in (100.0, 150.0):
        _create_invoice(
            client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
            subproject["subprojectId"], amount=amount,
        )

    info = client.get(
        f"/billing-info/subprojects/{subproject['subprojectId']}", headers=vendor_auth_headers
    ).json()
    assert info["totalInvoiced"] == "250.00"
    assert info["balanceDue"] == "250.00"


def test_new_invoice_after_full_payment_reopens_balance(client, test_project, test_user, vendor_auth_headers):
    """The stale case from the ticket: paid in full, then another invoice."""
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], amount=1000.0,
    )
    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 1000},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], amount=500.0,
    )

    info = client.get(
        f"/billing-info/subprojects/{subproject['subprojectId']}", headers=vendor_auth_headers
    ).json()
    assert info["totalInvoiced"] == "1500.00"
    assert info["totalPaid"] == "1000.00"
    assert info["balanceDue"] == "500.00"
    assert info["status"] == "partial_payment_received"


def test_project_level_invoice_does_not_create_billing_info(client, test_project, test_user, vendor_auth_headers):
    resp = client.post(
        "/invoices",
        json={
            "invoiceStatus": "Generated",
            "totalAmount": 100.0,
            "depositPercentage": 100,
            "invoiceAssignedTo": test_user["userId"],
            "projectAssociatedTo": test_project["projectId"],
        },
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    assert client.get("/billing-info", headers=vendor_auth_headers).json() == []


def _billing_info(client, subproject_id, headers):
    resp = client.get(f"/billing-info/subprojects/{subproject_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_updating_invoice_amount_updates_total_invoiced(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )

    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}", json={"totalAmount": 300.0}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["totalInvoiced"] == "300.00"
    assert info["balanceDue"] == "300.00"


def test_invoice_moved_before_acceptance_bills_its_new_subproject(
    client, test_project, test_user, vendor_auth_headers
):
    old = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    new = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, old["subprojectId"], accept=False
    )

    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}", json={"subprojectId": new["subprojectId"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    resp = client.patch(f"/invoices/{invoice['invoiceId']}/accept", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text

    assert _billing_info(client, old["subprojectId"], vendor_auth_headers)["status"] == "no_active_invoices"
    assert _billing_info(client, new["subprojectId"], vendor_auth_headers)["totalInvoiced"] == "100.00"


def test_detaching_invoice_from_subproject_updates_old_total(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], accept=False,
    )

    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}", json={"subprojectId": None}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["totalInvoiced"] == "0.00"
    assert info["balanceDue"] == "0.00"


def test_accepted_invoice_cannot_change_subproject(client, test_project, test_user, vendor_auth_headers):
    old = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    new = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, old["subprojectId"]
    )

    for subproject_id in (new["subprojectId"], None):
        resp = client.patch(
            f"/invoices/{invoice['invoiceId']}", json={"subprojectId": subproject_id}, headers=vendor_auth_headers
        )
        assert resp.status_code == 409, resp.text

    assert _billing_info(client, old["subprojectId"], vendor_auth_headers)["totalInvoiced"] == "100.00"


def test_paid_invoice_cannot_change_subproject(client, test_project, test_user, vendor_auth_headers):
    old = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    new = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, old["subprojectId"]
    )
    client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 40},
        headers=vendor_auth_headers,
    )

    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}", json={"subprojectId": new["subprojectId"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 409, resp.text


def test_accepted_invoice_can_still_be_edited_without_moving(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    client.patch(f"/invoices/{invoice['invoiceId']}", json={"invoiceStatus": "Accepted"}, headers=vendor_auth_headers)

    # sending the subproject it's already on isn't a move
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}",
        json={"subprojectId": subproject["subprojectId"], "dueDate": "2026-11-20T09:00:00"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text


def test_concurrent_payments_both_count_toward_total_paid(
    client, engine, test_project, test_user, vendor_auth_headers
):
    """Two payments recomputing at the same time: the second has to wait for
    the first to commit, then include it. Driven through two sessions
    directly, since the test client only sends one request at a time."""
    import threading
    from uuid import UUID

    from sqlalchemy.orm import Session

    from models import BillingHistory, BillingInfo
    from services.billing_history import _recompute_billing_info

    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    subproject_id = UUID(subproject["subprojectId"])
    invoice_id = UUID(invoice["invoiceId"])

    def pay(db, amount):
        db.add(
            BillingHistory(invoiceId=invoice_id, eventType="Payment_Succeeded", amount=amount, source="Manual")
        )
        db.flush()
        _recompute_billing_info(subproject_id, db)

    errors = []

    def second_payment():
        with Session(engine) as db:
            try:
                pay(db, 60)
                db.commit()
            except Exception as exc:  # surfaced in the main thread below
                errors.append(exc)

    # closed in finally: if an assertion fails while it holds the lock, the
    # table cleanup after the test would otherwise wait on it forever
    with Session(engine) as first:
        pay(first, 40)  # holds the lock until it commits
        thread = threading.Thread(target=second_payment)
        thread.start()
        thread.join(timeout=1)
        waited = thread.is_alive()
        first.commit()

    thread.join(timeout=10)
    assert waited, "second recompute didn't wait for the first one's lock"
    assert not thread.is_alive()
    assert not errors, errors

    with Session(engine) as db:
        info = db.get(BillingInfo, subproject_id)
        assert info.totalPaid == 100
        assert info.balanceDue == 0
        assert info.status == "paid_in_full"


# --- overdue: decided when read, from the earliest unpaid due date (ticket C6) ---

PAST = "2020-01-01T09:00:00"
FUTURE = "2099-01-01T09:00:00"


def _invoice_due(client, project_id, user_id, headers, subproject_id, due_date, amount=100.0, accept=True):
    resp = client.post(
        "/invoices",
        json={
            "invoiceStatus": "Generated",
            "totalAmount": amount,
            "depositPercentage": 100,
            "invoiceAssignedTo": user_id,
            "projectAssociatedTo": project_id,
            "subprojectId": subproject_id,
            "dueDate": due_date,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    if accept:
        resp = client.patch(f"/invoices/{resp.json()['invoiceId']}/accept", headers=headers)
        assert resp.status_code == 200, resp.text
    return resp.json()


def _pay(client, invoice_id, amount, headers):
    resp = client.post("/billing-history/payments", json={"invoiceId": invoice_id, "amount": amount}, headers=headers)
    assert resp.status_code == 200, resp.text


def test_past_due_invoice_with_balance_is_overdue(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    _invoice_due(client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"], PAST)

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["status"] == "overdue"
    assert info["nextDueDate"] is not None


def test_overdue_takes_precedence_over_partial_payment(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _invoice_due(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"], PAST
    )
    _pay(client, invoice["invoiceId"], 40, vendor_auth_headers)

    assert _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["status"] == "overdue"


def test_paid_invoice_past_due_is_not_overdue(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _invoice_due(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"], PAST
    )
    _pay(client, invoice["invoiceId"], 100, vendor_auth_headers)

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["status"] == "paid_in_full"
    assert info["nextDueDate"] is None


def test_future_due_date_is_not_overdue(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    _invoice_due(client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"], FUTURE)

    assert _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["status"] == "payment_pending"


def test_next_due_date_skips_paid_invoices(client, test_project, test_user, vendor_auth_headers):
    """A paid invoice past its due date doesn't count; the next one is unpaid but not due yet."""
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    paid = _invoice_due(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"], PAST
    )
    _pay(client, paid["invoiceId"], 100, vendor_auth_headers)
    unpaid = _invoice_due(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"], FUTURE
    )

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["status"] == "partial_payment_received"
    assert info["nextDueDate"] == unpaid["dueDate"]


def test_voiding_payment_makes_invoice_overdue_again(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _invoice_due(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"], PAST
    )
    _pay(client, invoice["invoiceId"], 100, vendor_auth_headers)
    payment = client.get(f"/billing-history/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers).json()[0]

    resp = client.post(
        f"/billing-history/{payment['id']}/void", json={"reason": "bounced"}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    assert _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["status"] == "overdue"


def test_rescheduling_keeps_next_due_date_of_accepted_invoices(
    client, test_project, test_user, vendor_auth_headers
):
    """Accepted invoices keep their due date when the event moves, so the
    summary's next due date stays put too."""
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    before = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["nextDueDate"]
    assert before == invoice["dueDate"]

    resp = client.patch(
        f"/subprojects/{subproject['subprojectId']}",
        json={"subprojectDate": "2026-12-11T19:00:00"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    assert _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["nextDueDate"] == before


def test_rescheduling_subproject_without_invoices_creates_no_billing_info(
    client, test_project, vendor_auth_headers
):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    resp = client.patch(
        f"/subprojects/{subproject['subprojectId']}",
        json={"subprojectDate": "2026-12-11T19:00:00"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = client.get(f"/billing-info/subprojects/{subproject['subprojectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 404


# --- no active invoices (ticket C6) -------------------------------------------

def test_deleting_every_invoice_means_no_active_invoices(client, test_project, test_user, vendor_auth_headers):
    """$0 owed because nothing is billed is not the same as paid in full."""
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], accept=False,
    )
    assert client.delete(f"/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers).status_code == 204

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["status"] == "no_active_invoices"
    assert info["totalInvoiced"] == "0.00"
    assert info["nextDueDate"] is None


def test_fully_paid_invoice_is_paid_in_full_not_no_active_invoices(
    client, test_project, test_user, vendor_auth_headers
):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    _pay(client, invoice["invoiceId"], 100, vendor_auth_headers)

    assert _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["status"] == "paid_in_full"


def test_new_invoice_after_all_deleted_is_pending_again(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], accept=False,
    )
    client.delete(f"/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers)
    _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )

    assert _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["status"] == "payment_pending"


def test_moving_only_invoice_away_leaves_no_active_invoices(client, test_project, test_user, vendor_auth_headers):
    old = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    new = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, old["subprojectId"], accept=False
    )
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}", json={"subprojectId": new["subprojectId"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    assert _billing_info(client, old["subprojectId"], vendor_auth_headers)["status"] == "no_active_invoices"


# --- only accepted invoices are billed (ticket C6, model A) ------------------

def test_unaccepted_past_due_invoice_is_not_overdue(client, test_project, test_user, vendor_auth_headers):
    """The client hasn't agreed to pay it yet, so it can't be late."""
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    _invoice_due(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], PAST, accept=False,
    )

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["status"] == "no_active_invoices"
    assert info["nextDueDate"] is None


def test_only_accepted_invoices_count_toward_total(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], amount=100.0,
    )
    _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], amount=500.0, accept=False,
    )

    assert _billing_info(client, subproject["subprojectId"], vendor_auth_headers)["totalInvoiced"] == "100.00"


def test_declined_invoice_is_not_billed(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], accept=False,
    )

    resp = client.patch(f"/invoices/{invoice['invoiceId']}/reject", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text

    info = _billing_info(client, subproject["subprojectId"], vendor_auth_headers)
    assert info["status"] == "no_active_invoices"
    assert info["totalInvoiced"] == "0.00"


@pytest.mark.parametrize("status", ["Accepted", "Pending", "Paid", "Declined"])
def test_only_unaccepted_invoices_can_be_rejected(client, test_project, test_user, vendor_auth_headers, status):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], accept=False,
    )
    client.patch(f"/invoices/{invoice['invoiceId']}", json={"invoiceStatus": status}, headers=vendor_auth_headers)

    resp = client.patch(f"/invoices/{invoice['invoiceId']}/reject", headers=vendor_auth_headers)
    assert resp.status_code == 409, resp.text
    assert f"{status} invoices can't be rejected" in resp.json()["detail"]


@pytest.mark.parametrize("status", ["Pending", "Paid"])
def test_invoices_past_acceptance_cannot_be_deleted_or_moved(
    client, test_project, test_user, vendor_auth_headers, status
):
    old = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    new = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, old["subprojectId"], accept=False
    )
    client.patch(f"/invoices/{invoice['invoiceId']}", json={"invoiceStatus": status}, headers=vendor_auth_headers)

    assert client.delete(f"/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers).status_code == 409
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}", json={"subprojectId": new["subprojectId"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 409, resp.text

