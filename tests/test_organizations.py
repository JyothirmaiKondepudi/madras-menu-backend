import uuid

from sqlalchemy import text


def _org_body(**overrides):
    body = {
        "orgId": str(uuid.uuid4()),
        "orgName": "Test Caterers",
        "orgCreatedAt": "2026-10-01T12:00:00",
        "orgEmail": f"org-{uuid.uuid4().hex[:8]}@example.com",
        "orgDisabled": False,
    }
    body.update(overrides)
    return body


def _create_org(client, headers, **overrides):
    resp = client.post("/organizations", json=_org_body(**overrides), headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _join_org(engine, user_id, org_id):
    # no API sets user_org yet, so link the user directly
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE user_data SET user_org = :org WHERE user_id = :user"),
            {"org": org_id, "user": user_id},
        )


def _client_headers(client, email):
    resp = client.post("/auth/login", json={"email": email, "password": "correct-horse-battery-staple"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_create_organization(client, vendor_auth_headers):
    body = _org_body(orgName="Madras Catering")
    resp = client.post("/organizations", json=body, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["orgId"] == body["orgId"]
    assert resp.json()["orgName"] == "Madras Catering"
    assert resp.json()["orgDisabled"] is False


def test_create_organization_with_duplicate_email_returns_409(client, vendor_auth_headers):
    _create_org(client, vendor_auth_headers, orgEmail="dupe@example.com")
    resp = client.post("/organizations", json=_org_body(orgEmail="dupe@example.com"), headers=vendor_auth_headers)
    assert resp.status_code == 409


def test_create_organization_requires_vendor(client, test_client_login):
    headers = _client_headers(client, test_client_login["userEmail"])
    assert client.post("/organizations", json=_org_body(), headers=headers).status_code == 403


def test_organizations_require_auth(client):
    assert client.post("/organizations", json=_org_body()).status_code == 401
    assert client.get(f"/organizations/{uuid.uuid4()}").status_code == 401


def test_get_own_organization(client, engine, vendor_auth_headers, test_vendor_login):
    org = _create_org(client, vendor_auth_headers, orgName="Own Org")
    _join_org(engine, test_vendor_login["userId"], org["orgId"])

    resp = client.get(f"/organizations/{org['orgId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["orgName"] == "Own Org"


def test_get_another_organization_forbidden(client, engine, vendor_auth_headers, test_vendor_login):
    own = _create_org(client, vendor_auth_headers)
    other = _create_org(client, vendor_auth_headers)
    _join_org(engine, test_vendor_login["userId"], own["orgId"])

    assert client.get(f"/organizations/{other['orgId']}", headers=vendor_auth_headers).status_code == 403


def test_list_all_organizations_not_granted_to_vendor(client, vendor_auth_headers):
    # org:view_all is deliberately withheld from vendors (see auth/permissions.py)
    assert client.get("/organizations/all", headers=vendor_auth_headers).status_code == 403


def test_update_own_organization(client, engine, vendor_auth_headers, test_vendor_login):
    org = _create_org(client, vendor_auth_headers)
    _join_org(engine, test_vendor_login["userId"], org["orgId"])

    resp = client.patch(
        f"/organizations/{org['orgId']}", json={"orgName": "Renamed", "orgDisabled": True}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["orgName"] == "Renamed"
    assert resp.json()["orgDisabled"] is True
    assert resp.json()["orgEmail"] == org["orgEmail"]


def test_update_another_organization_forbidden(client, engine, vendor_auth_headers, test_vendor_login):
    own = _create_org(client, vendor_auth_headers)
    other = _create_org(client, vendor_auth_headers, orgName="Other")
    _join_org(engine, test_vendor_login["userId"], own["orgId"])

    resp = client.patch(f"/organizations/{other['orgId']}", json={"orgName": "Hijacked"}, headers=vendor_auth_headers)
    assert resp.status_code == 403


def test_delete_organization(client, vendor_auth_headers):
    org = _create_org(client, vendor_auth_headers)
    assert client.delete(f"/organizations/{org['orgId']}", headers=vendor_auth_headers).status_code == 204


def test_delete_nonexistent_organization_returns_404(client, vendor_auth_headers):
    assert client.delete(f"/organizations/{uuid.uuid4()}", headers=vendor_auth_headers).status_code == 404
