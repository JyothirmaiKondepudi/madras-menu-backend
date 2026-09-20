def _invoice_body(project_id, user_id, **overrides):
    body = {
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }
    body.update(overrides)
    return body


def test_create_invoice(client, test_user, test_project, admin_auth_headers):
    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], invoiceAmount=2500.0),
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAmount"] == 2500.0
    assert resp.json()["project"]["projectId"] == test_project["projectId"]


def test_create_invoice_requires_admin(client, test_user, test_project, test_client_login):
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


def test_get_invoice_by_id(client, test_user, test_project, admin_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=admin_auth_headers
    ).json()

    resp = client.get(f"/invoices/{created['invoiceId']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["invoiceId"] == created["invoiceId"]


def test_get_nonexistent_invoice_returns_404(client, admin_auth_headers):
    resp = client.get("/invoices/00000000-0000-0000-0000-000000000000", headers=admin_auth_headers)
    assert resp.status_code == 404


def test_get_invoices_requires_auth(client):
    assert client.get("/invoices").status_code == 401


def test_client_only_sees_own_invoices(client, test_user, test_project, test_client_login, admin_auth_headers):
    client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=admin_auth_headers
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
    client, test_user, test_project, test_client_login, admin_auth_headers
):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=admin_auth_headers
    ).json()
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get(f"/invoices/{created['invoiceId']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_invoices_by_project_id(client, test_user, test_project, admin_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=admin_auth_headers
    ).json()

    resp = client.get(f"/invoices/projects/{test_project['projectId']}", headers=admin_auth_headers)
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


def test_update_invoice(client, test_user, test_project, admin_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=admin_auth_headers
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}", json={"invoiceStatus": "Paid"}, headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Paid"


def test_update_invoice_regenerates_pdf(client, test_user, test_project, admin_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], invoiceAmount=100.0),
        headers=admin_auth_headers,
    ).json()

    original_pdf = client.get(f"/invoices/{created['invoiceId']}/pdf", headers=admin_auth_headers).content

    client.patch(
        f"/invoices/{created['invoiceId']}", json={"invoiceAmount": 999.0}, headers=admin_auth_headers
    )

    updated_pdf = client.get(f"/invoices/{created['invoiceId']}/pdf", headers=admin_auth_headers).content
    # reportlab compresses its content stream, so the literal "999.00" isn't
    # visible in the raw bytes — checking the file actually changed is the
    # reliable signal that update_invoice_by_invoice_id really regenerated it.
    assert updated_pdf != original_pdf


def test_delete_invoice(client, test_user, test_project, admin_auth_headers):
    created = client.post(
        "/invoices", json=_invoice_body(test_project["projectId"], test_user["userId"]), headers=admin_auth_headers
    ).json()

    resp = client.delete(f"/invoices/{created['invoiceId']}", headers=admin_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/invoices/{created['invoiceId']}", headers=admin_auth_headers).status_code == 404


def test_invoice_pdf_generated_and_downloadable(client, test_user, test_project, admin_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], invoiceAmount=250.0),
        headers=admin_auth_headers,
    ).json()

    resp = client.get(f"/invoices/{created['invoiceId']}/pdf", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_invoice_pdf_requires_auth(client, test_user, test_project, admin_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], invoiceAmount=250.0),
        headers=admin_auth_headers,
    ).json()

    assert client.get(f"/invoices/{created['invoiceId']}/pdf").status_code == 401


def test_invoice_pdf_forbidden_for_another_user(
    client, test_user, test_project, test_client_login, admin_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"], invoiceAmount=250.0),
        headers=admin_auth_headers,
    ).json()
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get(f"/invoices/{created['invoiceId']}/pdf", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def _project_with_admin_and_client(client, admin_id, client_id, headers):
    return client.post("/projects", json={
        "projectName": "Notification Test Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "adminOnProject": admin_id,
        "clientId": client_id,
    }, headers=headers).json()


def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_client_accepting_invoice_notifies_both_client_and_admin(
    client, test_admin_login, test_client_login, admin_auth_headers
):
    project = _project_with_admin_and_client(
        client, test_admin_login["userId"], test_client_login["userId"], admin_auth_headers
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=admin_auth_headers,
    ).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/accept", headers={"Authorization": f"Bearer {client_token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Accepted"

    # both the client (who acted) and the project's admin should now be flagged
    client_me = client.get("/auth/me", headers={"Authorization": f"Bearer {client_token}"}).json()
    assert client_me["hasNotification"] is True

    admin_token = _login(client, test_admin_login["userEmail"])
    admin_me = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert admin_me["hasNotification"] is True


def test_reject_invoice_sets_declined_status(
    client, test_admin_login, test_client_login, admin_auth_headers
):
    project = _project_with_admin_and_client(
        client, test_admin_login["userId"], test_client_login["userId"], admin_auth_headers
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=admin_auth_headers,
    ).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/reject", headers={"Authorization": f"Bearer {client_token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Declined"


def test_accept_invoice_requires_being_the_billed_client_or_admin(
    client, test_user, test_project, test_client_login, admin_auth_headers
):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=admin_auth_headers,
    ).json()

    other_token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}/accept", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 403


def test_accept_invoice_requires_auth(client, test_user, test_project, admin_auth_headers):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=admin_auth_headers,
    ).json()

    assert client.patch(f"/invoices/{invoice['invoiceId']}/accept").status_code == 401


def test_clear_notification(client, test_client_login, test_admin_login, admin_auth_headers):
    project = _project_with_admin_and_client(
        client, test_admin_login["userId"], test_client_login["userId"], admin_auth_headers
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=admin_auth_headers,
    ).json()
    client_token = _login(client, test_client_login["userEmail"])
    client.patch(f"/invoices/{invoice['invoiceId']}/accept", headers={"Authorization": f"Bearer {client_token}"})

    resp = client.patch(
        "/auth/clear-notification", headers={"Authorization": f"Bearer {client_token}"}
    )
    assert resp.status_code == 204

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {client_token}"}).json()
    assert me["hasNotification"] is False
