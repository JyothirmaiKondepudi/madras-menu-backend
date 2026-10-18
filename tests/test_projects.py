def test_create_project(client, test_user, vendor_auth_headers):
    resp = client.post(
        "/projects",
        json={
            "projectName": "Wedding Reception",
            "projectStatus": "Proposal",
            "projectStartDate": "2026-11-14T18:00:00",
            "projectEndDate": "2026-11-14T23:00:00",
            "vendorOnProject": test_user["userId"],
        },
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["projectName"] == "Wedding Reception"


def _invoice_body(project_id, user_id, **overrides):
    body = {
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }
    body.update(overrides)
    return body


def test_create_project_requires_vendor(client, test_user, test_client_login):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/projects",
        json={
            "projectName": "Should Not Be Created",
            "projectStatus": "Proposal",
            "projectStartDate": "2026-11-14T18:00:00",
            "projectEndDate": "2026-11-14T23:00:00",
            "vendorOnProject": test_user["userId"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_project_includes_nested_clients_and_vendor(
    client, test_user, test_project, vendor_auth_headers
):
    resp = client.get(
        f"/projects/{test_project['projectId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [c["userId"] for c in body["clients"]] == [test_user["userId"]]
    assert body["vendor"]["userId"] == test_project["vendorOnProject"]


def test_get_nonexistent_project_returns_404(client, vendor_auth_headers):
    resp = client.get(
        "/projects/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_get_project_requires_auth(client, test_project):
    assert client.get(f"/projects/{test_project['projectId']}").status_code == 401


def test_get_project_forbidden_for_unlinked_client(
    client, test_project, test_client_login
):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]
    resp = client.get(
        f"/projects/{test_project['projectId']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_projects_by_user_id(client, test_user, test_project, vendor_auth_headers):
    resp = client.get(
        f"/users/{test_user['userId']}/projects", headers=vendor_auth_headers
    )
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_get_projects_by_user_id_forbidden_for_another_user(
    client, test_user, test_project, test_client_login
):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]
    resp = client.get(
        f"/users/{test_user['userId']}/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_delete_project(client, test_project, vendor_auth_headers):
    resp = client.delete(
        f"/projects/{test_project['projectId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 204
    assert (
        client.get(
            f"/projects/{test_project['projectId']}", headers=vendor_auth_headers
        ).status_code
        == 404
    )


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

    # read back in a new request: the PATCH response alone would look right
    # even if the route never committed
    resp = client.get(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.json()["projectName"] == "Renamed Project"


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


def test_add_user_to_project_then_client_sees_it(
    client, test_client_login, test_project, vendor_auth_headers
):
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


def test_add_user_to_project_is_idempotent(
    client, test_client_login, test_project, vendor_auth_headers
):
    url = f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}"
    assert client.post(url, headers=vendor_auth_headers).status_code == 200
    # linking the same user again should not error
    assert client.post(url, headers=vendor_auth_headers).status_code == 200


def test_add_user_to_project_nonexistent_project_404(
    client, test_client_login, vendor_auth_headers
):
    resp = client.post(
        f"/projects/00000000-0000-0000-0000-000000000000/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_set_final_invoice_rejects_deleted_invoice(
    client, test_user, test_project, vendor_auth_headers
):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    deleted_invoice = client.delete(
        f"/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers
    )
    assert deleted_invoice.status_code == 204
    # try to attach the deleted invoice to a project
    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice['invoiceId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_add_user_to_project_nonexistent_user_404(
    client, test_project, vendor_auth_headers
):
    resp = client.post(
        f"/projects/{test_project['projectId']}/users/00000000-0000-0000-0000-000000000000",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def _create_invoice(client, project_id, user_id, headers):
    return client.post(
        "/invoices",
        json={
            "totalAmount": 100.0,
            "depositPercentage": 100,
            "invoiceAssignedTo": user_id,
            "projectAssociatedTo": project_id,
        },
        headers=headers,
    ).json()


def test_set_final_invoice(client, test_user, test_project, vendor_auth_headers):
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers
    )

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice['invoiceId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["finalInvoiceId"] == invoice["invoiceId"]


def test_final_invoice_is_saved(client, test_user, test_project, vendor_auth_headers):
    # read back in a new request: the PATCH response alone would look right
    # even if the route never committed
    invoice = _create_invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice['invoiceId']}",
        headers=vendor_auth_headers,
    )

    resp = client.get(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["finalInvoiceId"] == invoice["invoiceId"]


def test_set_final_invoice_rejects_invoice_from_another_project(
    client, test_user, test_project, vendor_auth_headers
):
    other_project = client.post(
        "/projects",
        json={
            "projectName": "Other Project",
            "projectStatus": "Proposal",
            "projectStartDate": "2026-11-14T18:00:00",
            "projectEndDate": "2026-11-14T23:00:00",
            "vendorOnProject": test_user["userId"],
        },
        headers=vendor_auth_headers,
    ).json()
    client.post(
        f"/projects/{other_project['projectId']}/users/{test_user['userId']}",
        headers=vendor_auth_headers,
    )
    invoice_for_other_project = _create_invoice(
        client, other_project["projectId"], test_user["userId"], vendor_auth_headers
    )

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice_for_other_project['invoiceId']}",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 400


def test_set_final_invoice_requires_vendor(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    invoice = _create_invoice(
        client, test_project["projectId"], test_user["userId"], vendor_auth_headers
    )
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/{invoice['invoiceId']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_set_final_invoice_nonexistent_invoice_404(
    client, test_project, vendor_auth_headers
):
    resp = client.patch(
        f"/projects/{test_project['projectId']}/final-invoice/00000000-0000-0000-0000-000000000000",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_project_created_without_clients(client, test_user, vendor_auth_headers):
    resp = client.post(
        "/projects",
        json={
            "projectName": "No Client Yet",
            "projectStatus": "Proposal",
            "projectStartDate": "2026-11-14T18:00:00",
            "projectEndDate": "2026-11-14T23:00:00",
            "vendorOnProject": test_user["userId"],
        },
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["clients"] == []


def test_linked_client_sees_project_on_every_route(
    client, test_client_login, test_project, vendor_auth_headers
):
    client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )
    headers = {
        "Authorization": f"Bearer {_login(client, test_client_login['userEmail'])}"
    }

    listed = client.get("/projects", headers=headers).json()
    by_user = client.get(
        f"/users/{test_client_login['userId']}/projects", headers=headers
    ).json()
    assert [p["projectId"] for p in listed] == [test_project["projectId"]]
    assert [p["projectId"] for p in by_user] == [test_project["projectId"]]
    assert (
        client.get(
            f"/projects/{test_project['projectId']}", headers=headers
        ).status_code
        == 200
    )


def test_project_can_have_several_clients(
    client, test_user, test_client_login, test_project, vendor_auth_headers
):
    resp = client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )
    assert {c["userId"] for c in resp.json()["clients"]} == {
        test_user["userId"],
        test_client_login["userId"],
    }


def test_deleting_project_with_clients(client, test_project, vendor_auth_headers):
    # user_projects links cascade, so they never block the delete
    resp = client.delete(
        f"/projects/{test_project['projectId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 204


def test_project_audit_timestamps(client, test_project, vendor_auth_headers):
    from datetime import datetime

    created = datetime.fromisoformat(test_project["createdAt"])
    updated = datetime.fromisoformat(test_project["updatedAt"])
    assert created.tzinfo is not None and updated.tzinfo is not None

    resp = client.patch(
        f"/projects/{test_project['projectId']}",
        json={"projectName": "Renamed"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert datetime.fromisoformat(resp.json()["createdAt"]) == created
    assert datetime.fromisoformat(resp.json()["updatedAt"]) > updated


# --- a client never sees the project's other clients (BE-13) ---------------


def _shared_project(client, test_project, test_client_login, vendor_auth_headers):
    """Puts a second client on test_project next to test_client_login, and
    returns (that other client, test_client_login's auth headers)."""
    other = client.post("/users", json={
        "fullName": "Other Client",
        "email": "other.client@example.com",
        "phoneNumber": "5559871234",
        "role": "client",
    }, headers=vendor_auth_headers).json()
    for user_id in (other["userId"], test_client_login["userId"]):
        client.post(f"/projects/{test_project['projectId']}/users/{user_id}", headers=vendor_auth_headers)
    auth = {"Authorization": f"Bearer {_login(client, test_client_login['userEmail'])}"}
    return other, auth


def test_client_sees_only_themselves_on_a_shared_project(
    client, test_project, test_client_login, vendor_auth_headers
):
    other, client_auth = _shared_project(client, test_project, test_client_login, vendor_auth_headers)

    resp = client.get(f"/projects/{test_project['projectId']}", headers=client_auth)
    assert [c["userId"] for c in resp.json()["clients"]] == [test_client_login["userId"]]
    # nothing of the other client leaks anywhere in the response
    assert other["userEmail"] not in resp.text
    assert other["userPhoneNumber"] not in resp.text

    listed = client.get("/projects", headers=client_auth).json()
    [same] = [p for p in listed if p["projectId"] == test_project["projectId"]]
    assert [c["userId"] for c in same["clients"]] == [test_client_login["userId"]]


def test_vendor_still_sees_every_client(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    other, _ = _shared_project(client, test_project, test_client_login, vendor_auth_headers)
    project = client.get(f"/projects/{test_project['projectId']}", headers=vendor_auth_headers).json()
    assert {c["userId"] for c in project["clients"]} == {
        test_user["userId"], other["userId"], test_client_login["userId"],
    }
    # with their contact details
    [shown] = [c for c in project["clients"] if c["userId"] == other["userId"]]
    assert shown["userEmail"] == other["userEmail"]
    assert shown["userPhoneNumber"] == other["userPhoneNumber"]


def test_other_clients_hidden_inside_invoice_and_subproject_responses(
    client, test_project, test_client_login, vendor_auth_headers
):
    # the project is nested in these responses, so the same rule must hold there
    other, client_auth = _shared_project(client, test_project, test_client_login, vendor_auth_headers)
    invoice = _create_invoice(
        client, test_project["projectId"], test_client_login["userId"], vendor_auth_headers
    )
    subproject = client.post("/subprojects", json={
        "subprojectName": "Reception",
        "projectAssociatedTo": test_project["projectId"],
        "subprojectDate": "2026-11-14T19:00:00",
        "guestCount": 100,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
    }, headers=vendor_auth_headers).json()

    for url in (f"/invoices/{invoice['invoiceId']}", f"/subprojects/{subproject['subprojectId']}"):
        resp = client.get(url, headers=client_auth)
        assert resp.status_code == 200, (url, resp.text)
        clients = resp.json()["project"]["clients"]
        assert [c["userId"] for c in clients] == [test_client_login["userId"]], url
        assert other["userEmail"] not in resp.text, url
