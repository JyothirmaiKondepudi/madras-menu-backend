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


def _create_invoice(client, project_id, user_id, headers, subproject_id, amount=100.0):
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

def test_creating_invoice_creates_billing_info(client, test_project, test_user, vendor_auth_headers):
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


def test_changing_invoice_subproject_updates_both(client, test_project, test_user, vendor_auth_headers):
    old = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    new = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, old["subprojectId"]
    )

    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}", json={"subprojectId": new["subprojectId"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    assert _billing_info(client, old["subprojectId"], vendor_auth_headers)["totalInvoiced"] == "0.00"
    assert _billing_info(client, new["subprojectId"], vendor_auth_headers)["totalInvoiced"] == "100.00"


def test_detaching_invoice_from_subproject_updates_old_total(client, test_project, test_user, vendor_auth_headers):
    subproject = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers, subproject["subprojectId"]
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
    client.patch(f"/invoices/{invoice['invoiceId']}", json={"invoiceStatus": "Accepted"}, headers=vendor_auth_headers)

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
    assert "Void them" in resp.json()["detail"]


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
