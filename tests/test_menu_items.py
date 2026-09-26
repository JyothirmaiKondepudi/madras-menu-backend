def test_create_menu_item(client, vendor_auth_headers):
    resp = client.post("/menu-items", json={
        "name": "Bombay Veg. Sandwiches",
        "course": "snack",
        "vegNonveg": "veg",
        "priceWeight": "light",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Bombay Veg. Sandwiches"
    assert resp.json()["active"] is True  # default applied


def test_create_menu_item_requires_vendor(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.post("/menu-items", json={
        "name": "Should Not Be Created",
        "course": "snack",
        "vegNonveg": "veg",
        "priceWeight": "light",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_menu_item_by_id(client, test_menu_item, vendor_auth_headers):
    resp = client.get(f"/menu-items/{test_menu_item['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == test_menu_item["id"]


def test_get_nonexistent_menu_item_returns_404(client, vendor_auth_headers):
    resp = client.get("/menu-items/does-not-exist", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_update_menu_item(client, test_menu_item, vendor_auth_headers):
    resp = client.patch(
        f"/menu-items/{test_menu_item['id']}", json={"active": False}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["active"] is False
    assert resp.json()["name"] == test_menu_item["name"]


def test_delete_menu_item(client, test_menu_item, vendor_auth_headers):
    resp = client.delete(f"/menu-items/{test_menu_item['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/menu-items/{test_menu_item['id']}", headers=vendor_auth_headers).status_code == 404
