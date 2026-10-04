def _invoice_body(project_id, user_id, **overrides):
    body = {
        "invoiceStatus": "Generated",
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }
    body.update(overrides)
    return body


def test_create_invoice(client, test_user, test_project, vendor_auth_headers):
    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=2500.0),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAmount"] == "2500.00"
    assert resp.json()["project"]["projectId"] == test_project["projectId"]


def test_create_invoice_requires_vendor(client, test_user, test_project, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_invoice_by_id(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=vendor_auth_headers
    ).json()

    resp = client.get(f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["invoiceId"] == created["invoiceId"]


def test_get_nonexistent_invoice_returns_404(client, vendor_auth_headers):
    resp = client.get("/invoices/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_get_invoices_requires_auth(client):
    assert client.get("/invoices").status_code == 401


def test_client_only_sees_own_invoices(client, test_user, test_project, test_client_login, vendor_auth_headers):
    client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=vendor_auth_headers
    )
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/invoices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_client_cannot_view_another_users_invoice(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=vendor_auth_headers
    ).json()
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get(f"/invoices/{created['invoiceId']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_invoices_by_project_id(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=vendor_auth_headers
    ).json()

    resp = client.get(f"/invoices/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert any(i["invoiceId"] == created["invoiceId"] for i in resp.json())


def test_get_invoices_by_project_id_forbidden_for_unlinked_client(
    client, test_project, test_client_login
):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get(
        f"/invoices/projects/{test_project['projectId']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_update_invoice(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=vendor_auth_headers
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}", json={"invoiceStatus": "Paid"}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Paid"


def test_update_invoice_regenerates_pdf(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=100.0),
        headers=vendor_auth_headers,
    ).json()

    original_pdf = client.get(f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers).content

    client.patch(
        f"/invoices/{created['invoiceId']}", json={"totalAmount": 999.0}, headers=vendor_auth_headers
    )

    updated_pdf = client.get(f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers).content
    # reportlab compresses content, so just check the file actually changed
    assert updated_pdf != original_pdf


def test_delete_invoice(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=vendor_auth_headers
    ).json()

    resp = client.delete(f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers).status_code == 404


def test_invoice_pdf_generated_and_downloadable(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=250.0),
        headers=vendor_auth_headers,
    ).json()

    resp = client.get(f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_invoice_pdf_requires_auth(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=250.0),
        headers=vendor_auth_headers,
    ).json()

    assert client.get(f"/invoices/{created['invoiceId']}/pdf").status_code == 401


def test_invoice_pdf_forbidden_for_another_user(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=250.0),
        headers=vendor_auth_headers,
    ).json()
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get(f"/invoices/{created['invoiceId']}/pdf", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def _project_with_vendor_and_client(client, vendor_id, client_id, headers):
    project = client.post("/projects", json={
        "projectName": "Notification Test Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": vendor_id,
    }, headers=headers).json()
    if client_id is not None:
        client.post(f"/projects/{project['projectId']}/users/{client_id}", headers=headers)
    return project


def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_client_accepting_invoice_notifies_both_client_and_vendor(
    client, test_vendor_login, test_client_login, vendor_auth_headers
):
    project = _project_with_vendor_and_client(
        client, test_vendor_login["userId"], test_client_login["userId"], vendor_auth_headers
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=vendor_auth_headers,
    ).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/accept", headers={"Authorization": f"Bearer {client_token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Accepted"

    # both the acting client and the project's vendor should get a notification
    client_unread = client.get(
        "/notifications/unread", headers={"Authorization": f"Bearer {client_token}"}
    ).json()
    assert any(n["type"] == "invoice_accepted" for n in client_unread)

    vendor_token = _login(client, test_vendor_login["userEmail"])
    vendor_unread = client.get(
        "/notifications/unread", headers={"Authorization": f"Bearer {vendor_token}"}
    ).json()
    assert any(n["type"] == "invoice_accepted" for n in vendor_unread)


def test_reject_invoice_sets_declined_status(
    client, test_vendor_login, test_client_login, vendor_auth_headers
):
    project = _project_with_vendor_and_client(
        client, test_vendor_login["userId"], test_client_login["userId"], vendor_auth_headers
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=vendor_auth_headers,
    ).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/reject", headers={"Authorization": f"Bearer {client_token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Declined"


def test_accept_invoice_requires_being_the_billed_client_or_vendor(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    other_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/accept", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 403


def test_accept_invoice_requires_auth(client, test_user, test_project, vendor_auth_headers):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    assert client.patch(f"/invoices/{invoice['invoiceId']}/accept").status_code == 401




def test_invoice_amount_is_deposit_percentage_of_total(client, test_user, test_project, vendor_auth_headers):
    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=10000.0, depositPercentage=25),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["invoiceAmount"] == "2500.00"
    assert body["totalAmount"] == "10000.00"
    assert body["depositPercentage"] == "25.00"


def test_invoice_amount_rounds_to_the_cent(client, test_user, test_project, vendor_auth_headers):
    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=1000.0, depositPercentage=33.33),
        headers=vendor_auth_headers,
    )
    assert resp.json()["invoiceAmount"] == "333.30"


def test_deposit_percentage_out_of_range_rejected(client, test_user, test_project, vendor_auth_headers):
    for pct in (0, -5, 150):
        resp = client.post(
            "/invoices",
            json=_invoice_body(test_project["projectId"], test_user["userId"], depositPercentage=pct),
            headers=vendor_auth_headers,
        )
        assert resp.status_code == 422, pct


def test_updating_deposit_percentage_recomputes_amount(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], totalAmount=8000.0, depositPercentage=25),
        headers=vendor_auth_headers,
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}", json={"depositPercentage": 50}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAmount"] == "4000.00"
