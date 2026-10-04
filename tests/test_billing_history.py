def _subproject_body(project_id):
    return {
        "subprojectName": "Billing Test Subproject",
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


def _invoice_body(project_id, user_id, subproject_id=None, amount=100.0):
    body = {
        "invoiceStatus": "Generated",
        "totalAmount": amount,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }
    if subproject_id is not None:
        body["subprojectId"] = subproject_id
    return body


def _create_subproject(client, project_id, headers):
    resp = client.post("/subprojects", json=_subproject_body(project_id), headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_invoice(client, project_id, user_id, headers, subproject_id=None, amount=100.0):
    resp = client.post(
        "/invoices", json=_invoice_body(project_id, user_id, subproject_id, amount), headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_billing_history_requires_auth(client):
    assert client.get("/billing-history").status_code == 401


def test_record_payment_requires_vendor(client, test_project, test_user, vendor_auth_headers, test_client_login):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    token = _login(client, test_client_login["userEmail"])

    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_record_payment_nonexistent_invoice_404(client, vendor_auth_headers):
    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": "00000000-0000-0000-0000-000000000000", "amount": 50},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_record_payment_rejects_non_positive_amount(client, test_project, test_user, vendor_auth_headers):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 0},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 422


def test_record_payment_creates_billing_history_row(client, test_project, test_user, vendor_auth_headers):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)

    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 50, "billingMetadata": {"method": "check"}},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["eventType"] == "Payment_Succeeded"
    assert body["source"] == "Manual"
    assert body["amount"] == "50.00"
    assert body["billingMetadata"] == {"method": "check"}
    assert body["failureReason"] is None

    history = client.get(f"/billing-history/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers).json()
    assert len(history) == 1
    assert history[0]["id"] == body["id"]


def test_record_payment_without_subproject_skips_billing_info(client, test_project, test_user, vendor_auth_headers):
    """An invoice not tied to any subproject can still get a payment
    recorded — there's just nothing to summarize into billing_info."""
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    assert invoice["subprojectId"] is None

    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 50},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text


def test_record_partial_then_full_payment_updates_billing_info(
    client, test_project, test_user, vendor_auth_headers
):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers,
        subproject["subprojectId"], amount=100.0,
    )

    client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 60},
        headers=vendor_auth_headers,
    )
    info = client.get(
        f"/billing-info/subprojects/{subproject['subprojectId']}", headers=vendor_auth_headers
    ).json()
    assert info["totalInvoiced"] == "100.00"
    assert info["totalPaid"] == "60.00"
    assert info["balanceDue"] == "40.00"
    assert info["status"] == "partial_payment_received"

    client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 40},
        headers=vendor_auth_headers,
    )
    info = client.get(
        f"/billing-info/subprojects/{subproject['subprojectId']}", headers=vendor_auth_headers
    ).json()
    assert info["totalPaid"] == "100.00"
    assert info["balanceDue"] == "0.00"
    assert info["status"] == "paid_in_full"


def test_get_billing_history_for_nonexistent_subproject_404(client, vendor_auth_headers):
    resp = client.get(
        "/billing-history/subprojects/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_get_billing_history_for_invoice_forbidden_for_unrelated_client(
    client, test_project, test_user, vendor_auth_headers, test_client_login
):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 50},
        headers=vendor_auth_headers,
    )

    token = _login(client, test_client_login["userEmail"])
    resp = client.get(
        f"/billing-history/invoices/{invoice['invoiceId']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_client_only_sees_billing_history_for_linked_projects(
    client, test_project, test_user, vendor_auth_headers, test_client_login
):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
    )
    client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 50},
        headers=vendor_auth_headers,
    )

    token = _login(client, test_client_login["userEmail"])
    client_auth = {"Authorization": f"Bearer {token}"}

    assert client.get("/billing-history", headers=client_auth).json() == []
    resp = client.get(f"/billing-history/subprojects/{subproject['subprojectId']}", headers=client_auth)
    assert resp.status_code == 403

    client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )

    assert len(client.get("/billing-history", headers=client_auth).json()) == 1
    resp = client.get(f"/billing-history/subprojects/{subproject['subprojectId']}", headers=client_auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_record_payment_rejects_fractions_of_a_cent(client, test_project, test_user, vendor_auth_headers):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    resp = client.post(
        "/billing-history/payments",
        json={"invoiceId": invoice["invoiceId"], "amount": 10.005},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 422
