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
        json={"invoiceId": invoice["invoiceId"], "amount": 10000},
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
        json={"invoiceId": invoice["invoiceId"], "amount": 10000},
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
