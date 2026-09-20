def test_create_user(client, vendor_auth_headers):
    resp = client.post("/users", json={
        "fullName": "Jane Doe",
        "email": "jane@example.com",
        "phoneNumber": "5551234567",
        "preferredContact": "email",
        "address": "123 Main St",
        "role": "client",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fullName"] == "Jane Doe"
    assert body["userEmail"] == "jane@example.com"
    assert "userId" in body


def test_create_user_requires_vendor(client, test_user):
    resp = client.post("/users", json={
        "fullName": "Someone",
        "email": "someone@example.com",
        "phoneNumber": "5551110000",
        "preferredContact": "email",
        "role": "client",
    })
    assert resp.status_code == 401


def test_create_user_with_duplicate_email_returns_409(client, test_user, vendor_auth_headers):
    resp = client.post("/users", json={
        "fullName": "Someone Else",
        "email": test_user["userEmail"],
        "phoneNumber": "5559998888",
        "preferredContact": "email",
        "role": "client",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 409


def test_get_user_by_id(client, test_user, vendor_auth_headers):
    resp = client.get(f"/users/{test_user['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["userId"] == test_user["userId"]


def test_get_own_user_by_id_without_vendor(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get(
        f"/users/{test_client_login['userId']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


def test_get_another_users_id_forbidden(client, test_user, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get(f"/users/{test_user['userId']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_nonexistent_user_returns_404(client, vendor_auth_headers):
    resp = client.get("/users/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_update_user(client, test_user, vendor_auth_headers):
    resp = client.patch(
        f"/users/{test_user['userId']}", json={"fullName": "Updated Name"}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["fullName"] == "Updated Name"
    # untouched fields survive a partial update
    assert resp.json()["userEmail"] == test_user["userEmail"]


def test_update_nonexistent_user_returns_404(client, vendor_auth_headers):
    resp = client.patch(
        "/users/00000000-0000-0000-0000-000000000000", json={"fullName": "Nobody"}, headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_delete_user(client, test_user, vendor_auth_headers):
    resp = client.delete(f"/users/{test_user['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/users/{test_user['userId']}", headers=vendor_auth_headers).status_code == 404


def test_delete_nonexistent_user_returns_404(client, vendor_auth_headers):
    resp = client.delete("/users/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers)
    assert resp.status_code == 404
