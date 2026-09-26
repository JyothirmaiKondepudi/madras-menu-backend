def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _project(client, vendor_id, client_id, headers):
    return client.post("/projects", json={
        "projectName": "Notifications Test Project",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": vendor_id,
        "clientId": client_id,
    }, headers=headers).json()


def test_notifications_require_auth(client):
    assert client.get("/notifications/unread").status_code == 401


def test_creating_user_notifies_the_creator(client, vendor_auth_headers, test_vendor_login):
    # test_user (the plain no-password fixture) isn't used here on purpose —
    # we need to actually inspect the creating vendor's own notifications
    resp = client.post("/users", json={
        "fullName": "New Invitee",
        "email": "new.invitee@example.com",
        "phoneNumber": "5551112222",
        "preferredContact": "email",
        "role": "client",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    new_user_id = resp.json()["userId"]

    unread = client.get("/notifications/unread", headers=vendor_auth_headers).json()
    matching = [n for n in unread if n["type"] == "user_created" and n["relatedUserId"] == new_user_id]
    assert len(matching) == 1
    assert "New Invitee" in matching[0]["message"]


def test_invoice_generated_notifies_the_billed_client(client, test_user, test_project, vendor_auth_headers, test_client_login):
    # link test_client_login to test_project so we can log in as the
    # invoice's own assignee and check their unread notifications directly
    resp = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 500.0,
        "invoiceAssignedTo": test_client_login["userId"],
        "projectAssociatedTo": test_project["projectId"],
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    invoice_id = resp.json()["invoiceId"]

    client_token = _login(client, test_client_login["userEmail"])
    unread = client.get("/notifications/unread", headers={"Authorization": f"Bearer {client_token}"}).json()
    matching = [n for n in unread if n["type"] == "invoice_generated" and n["relatedInvoiceId"] == invoice_id]
    assert len(matching) == 1


def test_mark_notification_read_sets_both_seen_and_read(client, test_user, test_project, vendor_auth_headers, test_client_login):
    resp = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": test_client_login["userId"],
        "projectAssociatedTo": test_project["projectId"],
    }, headers=vendor_auth_headers)
    invoice_id = resp.json()["invoiceId"]

    client_token = _login(client, test_client_login["userEmail"])
    client_auth = {"Authorization": f"Bearer {client_token}"}
    unread = client.get("/notifications/unread", headers=client_auth).json()
    notification = next(n for n in unread if n["relatedInvoiceId"] == invoice_id)
    assert notification["seenAt"] is None
    assert notification["readAt"] is None

    marked = client.patch(f"/notifications/{notification['id']}/read", headers=client_auth)
    assert marked.status_code == 200, marked.text
    assert marked.json()["seenAt"] is not None
    assert marked.json()["readAt"] is not None

    # read notifications drop out of the unread list
    unread_after = client.get("/notifications/unread", headers=client_auth).json()
    assert notification["id"] not in [n["id"] for n in unread_after]


def test_mark_notification_seen_does_not_mark_it_read(client, test_user, test_project, vendor_auth_headers, test_client_login):
    resp = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": test_client_login["userId"],
        "projectAssociatedTo": test_project["projectId"],
    }, headers=vendor_auth_headers)
    invoice_id = resp.json()["invoiceId"]

    client_token = _login(client, test_client_login["userEmail"])
    client_auth = {"Authorization": f"Bearer {client_token}"}
    unread = client.get("/notifications/unread", headers=client_auth).json()
    notification = next(n for n in unread if n["relatedInvoiceId"] == invoice_id)

    marked = client.patch(f"/notifications/{notification['id']}/seen", headers=client_auth)
    assert marked.status_code == 200, marked.text
    assert marked.json()["seenAt"] is not None
    assert marked.json()["readAt"] is None

    # still unread, since seeing something isn't the same as reading it
    unread_after = client.get("/notifications/unread", headers=client_auth).json()
    assert notification["id"] in [n["id"] for n in unread_after]


def test_cannot_mark_another_users_notification(client, test_vendor_login, test_client_login, vendor_auth_headers):
    project = _project(client, test_vendor_login["userId"], test_client_login["userId"], vendor_auth_headers)
    resp = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": test_client_login["userId"],
        "projectAssociatedTo": project["projectId"],
    }, headers=vendor_auth_headers)
    invoice_id = resp.json()["invoiceId"]

    client_token = _login(client, test_client_login["userEmail"])
    unread = client.get(
        "/notifications/unread", headers={"Authorization": f"Bearer {client_token}"}
    ).json()
    notification = next(n for n in unread if n["relatedInvoiceId"] == invoice_id)

    # a second, unrelated client tries to mark someone else's notification
    other_resp = client.post("/users", json={
        "fullName": "Unrelated Client",
        "email": "unrelated.client@example.com",
        "phoneNumber": "5559990000",
        "preferredContact": "email",
        "role": "client",
        "password": "correct-horse-battery-staple",
    }, headers=vendor_auth_headers)
    other_token = _login(client, other_resp.json()["userEmail"])

    resp = client.patch(
        f"/notifications/{notification['id']}/read", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 403


def test_mark_nonexistent_notification_404(client, test_client_login):
    token = _login(client, test_client_login["userEmail"])
    resp = client.patch(
        "/notifications/00000000-0000-0000-0000-000000000000/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
