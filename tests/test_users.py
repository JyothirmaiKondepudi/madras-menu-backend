def test_create_user(client):
    resp = client.post("/users", json={
        "fullName": "Jane Doe",
        "email": "jane@example.com",
        "phoneNumber": "5551234567",
        "preferredContact": "email",
        "address": "123 Main St",
        "role": "client",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fullName"] == "Jane Doe"
    assert body["userEmail"] == "jane@example.com"
    assert "userId" in body


def test_create_user_with_duplicate_email_returns_409(client, test_user):
    resp = client.post("/users", json={
        "fullName": "Someone Else",
        "email": test_user["userEmail"],
        "phoneNumber": "5559998888",
        "preferredContact": "email",
        "role": "client",
    })
    assert resp.status_code == 409


def test_get_user_by_id(client, test_user):
    resp = client.get(f"/users/{test_user['userId']}")
    assert resp.status_code == 200
    assert resp.json()["userId"] == test_user["userId"]


def test_get_nonexistent_user_returns_404(client):
    resp = client.get("/users/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_update_user(client, test_user):
    resp = client.patch(f"/users/{test_user['userId']}", json={"fullName": "Updated Name"})
    assert resp.status_code == 200
    assert resp.json()["fullName"] == "Updated Name"
    # untouched fields survive a partial update
    assert resp.json()["userEmail"] == test_user["userEmail"]


def test_update_nonexistent_user_returns_404(client):
    resp = client.patch(
        "/users/00000000-0000-0000-0000-000000000000", json={"fullName": "Nobody"}
    )
    assert resp.status_code == 404


def test_delete_user(client, test_user):
    resp = client.delete(f"/users/{test_user['userId']}")
    assert resp.status_code == 204
    assert client.get(f"/users/{test_user['userId']}").status_code == 404


def test_delete_nonexistent_user_returns_404(client):
    resp = client.delete("/users/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
