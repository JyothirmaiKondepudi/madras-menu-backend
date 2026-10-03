def test_create_project(client, test_user, vendor_auth_headers):
    resp = client.post("/projects", json={
        "projectName": "Wedding Reception",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": test_user["userId"],
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["projectName"] == "Wedding Reception"


def test_create_project_requires_vendor(client, test_user, test_client_login):
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
        "vendorOnProject": test_user["userId"],
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_project_includes_nested_clients_and_vendor(client, test_user, test_project, vendor_auth_headers):
    resp = client.get(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [c["userId"] for c in body["clients"]] == [test_user["userId"]]
    assert body["vendor"]["userId"] == test_project["vendorOnProject"]


def test_get_nonexistent_project_returns_404(client, vendor_auth_headers):
    resp = client.get("/projects/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers)
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


def test_get_projects_by_user_id(client, test_user, test_project, vendor_auth_headers):
    resp = client.get(f"/projects/users/{test_user['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_get_projects_by_user_id_forbidden_for_another_user(client, test_user, test_project, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]
    resp = client.get(
        f"/projects/users/{test_user['userId']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_delete_project(client, test_project, vendor_auth_headers):
    resp = client.delete(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers).status_code == 404


def test_partial_update_project(client, test_project, vendor_auth_headers):
    """A PATCH should only require the field(s) actually being changed."""
    resp = client.patch(
        f"/projects/{test_project['projectId']}",
        json={"projectName": "Renamed Project"},
        headers=vendor_auth_headers,
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


def test_vendor_sees_all_projects(client, test_vendor_login, test_project):
    token = _login(client, test_vendor_login["userEmail"])
    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_client_sees_no_projects_until_linked(client, test_client_login, test_project):
    token = _login(client, test_client_login["userEmail"])
    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_user_to_project_then_client_sees_it(client, test_client_login, test_project, vendor_auth_headers):
    link_resp = client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )
    assert link_resp.status_code == 200, link_resp.text

    token = _login(client, test_client_login["userEmail"])
    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_add_user_to_project_requires_vendor(client, test_client_login, test_project):
    token = _login(client, test_client_login["userEmail"])
    resp = client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_add_user_to_project_is_idempotent(client, test_client_login, test_project, vendor_auth_headers):
    url = f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}"
    assert client.post(url, headers=vendor_auth_headers).status_code == 200
    # linking the same user again should not error
    assert client.post(url, headers=vendor_auth_headers).status_code == 200


def test_add_user_to_project_nonexistent_project_404(client, test_client_login, vendor_auth_headers):
    resp = client.post(
        f"/projects/00000000-0000-0000-0000-000000000000/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_add_user_to_project_nonexistent_user_404(client, test_project, vendor_auth_headers):
    resp = client.post(
        f"/projects/{test_project['projectId']}/users/00000000-0000-0000-0000-000000000000",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def _create_invoice(client, project_id, user_id, headers):
    return client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }, headers=headers).json()


def test_set_final_invoice(client, test_user, test_project, vendor_auth_headers):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice['invoiceId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["finalInvoiceId"] == invoice["invoiceId"]


def test_set_final_invoice_rejects_invoice_from_another_project(
    client, test_user, test_project, vendor_auth_headers
):
    other_project = client.post("/projects", json={
        "projectName": "Other Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": test_user["userId"],
    }, headers=vendor_auth_headers).json()
    invoice_for_other_project = _create_invoice(
        client, other_project["projectId"], test_user["userId"], vendor_auth_headers
    )

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice_for_other_project['invoiceId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 400


def test_set_final_invoice_requires_vendor(client, test_user, test_project, test_client_login, vendor_auth_headers):
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
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


def test_set_final_invoice_nonexistent_invoice_404(client, test_project, vendor_auth_headers):
    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/00000000-0000-0000-0000-000000000000",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_project_created_without_clients(client, test_user, vendor_auth_headers):
    resp = client.post("/projects", json={
        "projectName": "No Client Yet",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": test_user["userId"],
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["clients"] == []


def test_linked_client_sees_project_on_every_route(client, test_client_login, test_project, vendor_auth_headers):
    client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}", headers=vendor_auth_headers
    )
    headers = {"Authorization": f"Bearer {_login(client, test_client_login['userEmail'])}"}

    listed = client.get("/projects", headers=headers).json()
    by_user = client.get(f"/projects/users/{test_client_login['userId']}", headers=headers).json()
    assert [p["projectId"] for p in listed] == [test_project["projectId"]]
    assert [p["projectId"] for p in by_user] == [test_project["projectId"]]
    assert client.get(f"/projects/{test_project['projectId']}", headers=headers).status_code == 200


def test_project_can_have_several_clients(client, test_user, test_client_login, test_project, vendor_auth_headers):
    resp = client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}", headers=vendor_auth_headers
    )
    assert {c["userId"] for c in resp.json()["clients"]} == {test_user["userId"], test_client_login["userId"]}


def test_deleting_project_with_clients(client, test_project, vendor_auth_headers):
    # user_projects links cascade, so they never block the delete
    resp = client.delete(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
