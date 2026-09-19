def test_create_tax_category(client, admin_auth_headers):
    resp = client.post("/tax-categories", json={
        "name": "prepared_food",
        "jurisdiction": "FL",
        "ratePercent": 7.0,
    }, headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "prepared_food"


def test_tax_categories_require_admin(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/tax-categories", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_tax_category_by_id(client, admin_auth_headers):
    created = client.post("/tax-categories", json={
        "name": "alcohol", "jurisdiction": "FL", "ratePercent": 7.0,
    }, headers=admin_auth_headers).json()

    resp = client.get(f"/tax-categories/{created['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_nonexistent_tax_category_returns_404(client, admin_auth_headers):
    resp = client.get("/tax-categories/does-not-exist", headers=admin_auth_headers)
    assert resp.status_code == 404


def test_delete_tax_category(client, admin_auth_headers):
    created = client.post("/tax-categories", json={
        "name": "service_labor", "jurisdiction": "FL", "ratePercent": 0.0,
    }, headers=admin_auth_headers).json()

    resp = client.delete(f"/tax-categories/{created['id']}", headers=admin_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/tax-categories/{created['id']}", headers=admin_auth_headers).status_code == 404
