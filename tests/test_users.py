import pytest


def test_create_user(client, vendor_auth_headers):
    resp = client.post(
        "/users",
        json={
            "fullName": "Jane Doe",
            "email": "jane@example.com",
            "address": "123 Main St",
            "role": "client",
        },
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fullName"] == "Jane Doe"
    assert body["userEmail"] == "jane@example.com"
    assert "userId" in body
    assert body["preferredContact"] is None
    assert body["userPhoneNumber"] is None


def test_create_user_requires_vendor(client, test_user):
    resp = client.post(
        "/users",
        json={
            "fullName": "Someone",
            "email": "someone@example.com",
            "role": "client",
        },
    )
    assert resp.status_code == 401


def test_create_user_with_duplicate_email_returns_409(
    client, test_user, vendor_auth_headers
):
    resp = client.post(
        "/users",
        json={
            "fullName": "Someone Else",
            "email": test_user["userEmail"],
            "role": "client",
        },
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 409


def test_get_user_by_id(client, test_user, vendor_auth_headers):
    resp = client.get(f"/users/{test_user['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["userId"] == test_user["userId"]


def test_get_own_user_by_id_without_vendor(client, test_client_login):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.get(
        f"/users/{test_client_login['userId']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_get_another_users_id_forbidden(client, test_user, test_client_login):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.get(
        f"/users/{test_user['userId']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_get_nonexistent_user_returns_404(client, vendor_auth_headers):
    resp = client.get(
        "/users/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_update_user(client, test_user, vendor_auth_headers):
    resp = client.patch(
        f"/users/{test_user['userId']}",
        json={"fullName": "Updated Name"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["fullName"] == "Updated Name"
    # untouched fields survive a partial update
    assert resp.json()["userEmail"] == test_user["userEmail"]

    # read back in a new request: the PATCH response alone would look right
    # even if the route never committed
    resp = client.get(f"/users/{test_user['userId']}", headers=vendor_auth_headers)
    assert resp.json()["fullName"] == "Updated Name"


def test_update_nonexistent_user_returns_404(client, vendor_auth_headers):
    resp = client.patch(
        "/users/00000000-0000-0000-0000-000000000000",
        json={"fullName": "Nobody"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404


def test_delete_user(client, test_user, vendor_auth_headers):
    resp = client.delete(f"/users/{test_user['userId']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert (
        client.get(
            f"/users/{test_user['userId']}", headers=vendor_auth_headers
        ).status_code
        == 404
    )


def test_delete_nonexistent_user_returns_404(client, vendor_auth_headers):
    resp = client.delete(
        "/users/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_created_user_inherits_vendor_org(
    client, vendor_auth_headers, test_vendor_login
):
    resp = client.post(
        "/users",
        json={
            "fullName": "Org Member",
            "email": "org.member@example.com",
            "phoneNumber": "5551234567",
            "preferredContact": "email",
            "role": "client",
        },
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["userOrg"] == test_vendor_login["userOrg"]


def test_create_user_ignores_client_supplied_org(
    client, vendor_auth_headers, test_vendor_login
):
    resp = client.post(
        "/users",
        json={
            "fullName": "Org Hopper",
            "email": "org.hopper@example.com",
            "phoneNumber": "5551234567",
            "preferredContact": "email",
            "role": "client",
            "userOrg": "00000000-0000-0000-0000-000000000000",
        },
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["userOrg"] == test_vendor_login["userOrg"]


def _new_platform_admin_body(email):
    return {
        "fullName": "New Admin",
        "email": email,
        "phoneNumber": "5551234567",
        "preferredContact": "email",
        "role": "platform_admin",
    }


def test_vendor_cannot_create_platform_admin(client, vendor_auth_headers):
    resp = client.post(
        "/users",
        json=_new_platform_admin_body("sneaky.admin@example.com"),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 403


def test_platform_admin_can_create_platform_admin(client, platform_admin_headers):
    me = client.get("/auth/me", headers=platform_admin_headers).json()
    resp = client.post(
        "/users",
        json=_new_platform_admin_body("second.admin@example.com"),
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["userRole"] == "platform_admin"
    assert resp.json()["userOrg"] == me["userOrg"]  # lands in the platform's own org


def test_unknown_role_rejected(client, vendor_auth_headers):
    body = _new_platform_admin_body("wizard@example.com") | {"role": "wizard"}
    assert (
        client.post("/users", json=body, headers=vendor_auth_headers).status_code == 422
    )


# --- one account per email, whatever the capitalization ---------------------


def _new_client(client, headers, email, **extra):
    return client.post("/users", json={
        "fullName": "Case Test", "email": email, "role": "client", **extra,
    }, headers=headers)


def test_email_is_stored_lowercase(client, vendor_auth_headers):
    resp = _new_client(client, vendor_auth_headers, "  Jane.Case@Example.COM ")
    assert resp.status_code == 200, resp.text
    assert resp.json()["userEmail"] == "jane.case@example.com"


def test_same_email_in_different_case_is_a_duplicate(client, vendor_auth_headers):
    assert _new_client(client, vendor_auth_headers, "Jane.Case@Example.com").status_code == 200
    # used to create a second account that logged in as the first
    resp = _new_client(client, vendor_auth_headers, "jane.case@example.com")
    assert resp.status_code == 409, resp.text


def test_changing_email_to_another_users_in_different_case_is_rejected(
    client, test_user, vendor_auth_headers
):
    other = _new_client(client, vendor_auth_headers, "other.case@example.com").json()
    resp = client.patch(
        f"/users/{other['userId']}",
        json={"email": test_user["userEmail"].upper()},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 409, resp.text


def test_login_works_whatever_the_capitalization(client, vendor_auth_headers):
    _new_client(client, vendor_auth_headers, "Login.Case@Example.com", password="correct-horse-battery-staple")
    for typed in ("login.case@example.com", "LOGIN.CASE@EXAMPLE.COM"):
        resp = client.post("/auth/login", json={"email": typed, "password": "correct-horse-battery-staple"})
        assert resp.status_code == 200, (typed, resp.text)


def test_database_rejects_a_case_duplicate_that_skips_the_api(client, engine, test_user):
    # the unique index on lower(email) is the backstop for seed scripts and SQL
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError, match="user_data_email_lower_key"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO user_data (user_id, full_name, email, role, user_org, user_disabled) "
                    "SELECT gen_random_uuid(), 'Dup', upper(email), role, user_org, false "
                    "FROM user_data WHERE user_id = :id"
                ),
                {"id": test_user["userId"]},
            )


# --- preferredContact is email or phone ---------------------------------------


@pytest.mark.parametrize("choice", ["email", "phone"])
def test_preferred_contact_accepts_email_or_phone(client, vendor_auth_headers, choice):
    resp = _new_client(client, vendor_auth_headers, f"pref.{choice}@example.com", preferredContact=choice)
    assert resp.status_code == 200, resp.text
    assert resp.json()["preferredContact"] == choice


def test_preferred_contact_phone_doesnt_require_a_phone_number(client, vendor_auth_headers):
    # deliberately not enforced: it isn't known yet what the frontend requires
    resp = _new_client(client, vendor_auth_headers, "pref.nophone@example.com", preferredContact="phone")
    assert resp.status_code == 200, resp.text
    assert resp.json()["userPhoneNumber"] is None


def test_preferred_contact_rejects_anything_else(client, test_user, vendor_auth_headers):
    resp = _new_client(client, vendor_auth_headers, "pref.bad@example.com", preferredContact="carrier pigeon")
    assert resp.status_code == 422, resp.text

    resp = client.patch(
        f"/users/{test_user['userId']}", json={"preferredContact": "fax"}, headers=vendor_auth_headers
    )
    assert resp.status_code == 422, resp.text
