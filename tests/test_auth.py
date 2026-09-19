def test_login_success_returns_token(client, test_client_login):
    resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_wrong_password_401(client, test_client_login):
    resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "not-the-right-password",
    })
    assert resp.status_code == 401


def test_login_nonexistent_email_401(client):
    resp = client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "whatever",
    })
    assert resp.status_code == 401


def test_login_nonexistent_email_and_wrong_password_give_same_message(client, test_client_login):
    """Same generic detail either way, so a caller can't use the message to
    enumerate which emails have accounts."""
    wrong_password_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "not-the-right-password",
    })
    no_such_email_resp = client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "whatever",
    })
    assert wrong_password_resp.json()["detail"] == no_such_email_resp.json()["detail"]


def test_login_user_without_password_401(client, test_user):
    """test_user (from conftest) was created with no password at all —
    logging in as them should fail cleanly, not error."""
    resp = client.post("/auth/login", json={
        "email": test_user["userEmail"],
        "password": "anything",
    })
    assert resp.status_code == 401


def test_me_without_token_401(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_garbage_token_401(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_me_with_valid_token_200(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["userId"] == test_client_login["userId"]


def test_me_with_expired_token_401(client, test_client_login):
    from auth.security import create_access_token
    from uuid import UUID

    expired_token = create_access_token(UUID(test_client_login["userId"]), expires_minutes=-1)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


def test_change_password_success(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.patch(
        "/auth/change-password",
        json={"currentPassword": "correct-horse-battery-staple", "newPassword": "a-new-strong-password"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    old = client.post("/auth/login", json={
        "email": test_client_login["userEmail"], "password": "correct-horse-battery-staple",
    })
    assert old.status_code == 401

    new = client.post("/auth/login", json={
        "email": test_client_login["userEmail"], "password": "a-new-strong-password",
    })
    assert new.status_code == 200


def test_change_password_wrong_current_password_401(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.patch(
        "/auth/change-password",
        json={"currentPassword": "totally-wrong", "newPassword": "a-new-strong-password"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401

    # a rejected attempt must change nothing
    still_works = client.post("/auth/login", json={
        "email": test_client_login["userEmail"], "password": "correct-horse-battery-staple",
    })
    assert still_works.status_code == 200


def test_change_password_requires_auth(client):
    resp = client.patch(
        "/auth/change-password",
        json={"currentPassword": "whatever", "newPassword": "a-new-strong-password"},
    )
    assert resp.status_code == 401
