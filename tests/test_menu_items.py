def test_create_menu_item(client):
    resp = client.post("/menu-items", json={
        "name": "Bombay Veg. Sandwiches",
        "course": "snack",
        "vegNonveg": "veg",
        "priceWeight": "light",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Bombay Veg. Sandwiches"
    assert resp.json()["active"] is True  # default applied


def test_get_menu_item_by_id(client, test_menu_item):
    resp = client.get(f"/menu-items/{test_menu_item['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == test_menu_item["id"]


def test_get_nonexistent_menu_item_returns_404(client):
    resp = client.get("/menu-items/does-not-exist")
    assert resp.status_code == 404


def test_update_menu_item(client, test_menu_item):
    resp = client.patch(f"/menu-items/{test_menu_item['id']}", json={"active": False})
    assert resp.status_code == 200, resp.text
    assert resp.json()["active"] is False
    assert resp.json()["name"] == test_menu_item["name"]


def test_delete_menu_item(client, test_menu_item):
    resp = client.delete(f"/menu-items/{test_menu_item['id']}")
    assert resp.status_code == 204
    assert client.get(f"/menu-items/{test_menu_item['id']}").status_code == 404
