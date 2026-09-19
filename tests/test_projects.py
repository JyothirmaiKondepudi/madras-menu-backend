def test_create_project(client, test_user, admin_auth_headers):
    resp = client.post("/projects", json={
        "projectName": "Wedding Reception",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "adminOnProject": test_user["userId"],
        "clientId": test_user["userId"],
    }, headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["projectName"] == "Wedding Reception"


def test_create_project_requires_admin(client, test_user, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.post("/projects", json={
        "projectName": "Should Not Be Created",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "adminOnProject": test_user["userId"],
        "clientId": test_user["userId"],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_project_includes_nested_client_and_admin(client, test_project, admin_auth_headers):
    resp = client.get(f"/projects/{test_project['projectId']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["client"]["userId"] == test_project["clientId"]
    assert body["admin"]["userId"] == test_project["adminOnProject"]


def test_get_nonexistent_project_returns_404(client, admin_auth_headers):
    resp = client.get("/projects/00000000-0000-0000-0000-000000000000", headers=admin_auth_headers)
    assert resp.status_code == 404


def test_get_project_requires_auth(client, test_project):
    assert client.get(f"/projects/{test_project['projectId']}").status_code == 401


def test_get_project_forbidden_for_unlinked_client(client, test_project, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]
    resp = client.get(
        f"/projects/{test_project['projectId']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_get_projects_by_user_id(client, test_project, admin_auth_headers):
    resp = client.get(f"/projects/users/{test_project['clientId']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_get_projects_by_user_id_forbidden_for_another_user(client, test_project, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]
    resp = client.get(
        f"/projects/users/{test_project['clientId']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_delete_project(client, test_project, admin_auth_headers):
    resp = client.delete(f"/projects/{test_project['projectId']}", headers=admin_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/projects/{test_project['projectId']}", headers=admin_auth_headers).status_code == 404


def test_partial_update_project(client, test_project, admin_auth_headers):
    """A PATCH should only require the field(s) actually being changed."""
    resp = client.patch(
        f"/projects/{test_project['projectId']}",
        json={"projectName": "Renamed Project"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["projectName"] == "Renamed Project"
    # untouched fields survive
    assert resp.json()["projectStatus"] == test_project["projectStatus"]


def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_get_projects_requires_auth(client):
    assert client.get("/projects").status_code == 401


def test_admin_sees_all_projects(client, test_admin_login, test_project):
    token = _login(client, test_admin_login["userEmail"])
    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_client_sees_no_projects_until_linked(client, test_client_login, test_project):
    token = _login(client, test_client_login["userEmail"])
    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_user_to_project_then_client_sees_it(client, test_client_login, test_project, admin_auth_headers):
    link_resp = client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=admin_auth_headers,
    )
    assert link_resp.status_code == 200, link_resp.text

    token = _login(client, test_client_login["userEmail"])
    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_add_user_to_project_requires_admin(client, test_client_login, test_project):
    token = _login(client, test_client_login["userEmail"])
    resp = client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_add_user_to_project_is_idempotent(client, test_client_login, test_project, admin_auth_headers):
    url = f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}"
    assert client.post(url, headers=admin_auth_headers).status_code == 200
    # linking the same user again should not error (e.g. a duplicate-row
    # IntegrityError from user_projects' composite primary key)
    assert client.post(url, headers=admin_auth_headers).status_code == 200


def test_add_user_to_project_nonexistent_project_404(client, test_client_login, admin_auth_headers):
    resp = client.post(
        f"/projects/00000000-0000-0000-0000-000000000000/users/{test_client_login['userId']}",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


def test_add_user_to_project_nonexistent_user_404(client, test_project, admin_auth_headers):
    resp = client.post(
        f"/projects/{test_project['projectId']}/users/00000000-0000-0000-0000-000000000000",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


def _create_invoice(client, project_id, user_id, headers):
    return client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }, headers=headers).json()


def test_set_final_invoice(client, test_user, test_project, admin_auth_headers):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], admin_auth_headers)

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice['invoiceId']}",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["finalInvoiceId"] == invoice["invoiceId"]


def test_set_final_invoice_rejects_invoice_from_another_project(
    client, test_user, test_project, admin_auth_headers
):
    other_project = client.post("/projects", json={
        "projectName": "Other Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "adminOnProject": test_user["userId"],
        "clientId": test_user["userId"],
    }, headers=admin_auth_headers).json()
    invoice_for_other_project = _create_invoice(
        client, other_project["projectId"], test_user["userId"], admin_auth_headers
    )

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice_for_other_project['invoiceId']}",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


def test_set_final_invoice_requires_admin(client, test_user, test_project, test_client_login, admin_auth_headers):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], admin_auth_headers)
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice['invoiceId']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_set_final_invoice_nonexistent_invoice_404(client, test_project, admin_auth_headers):
    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/00000000-0000-0000-0000-000000000000",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
