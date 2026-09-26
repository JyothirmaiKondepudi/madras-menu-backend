"""Regression tests for main.py's global exception handlers — each one
maps to a real bug this session found and fixed, not a hypothetical."""


def test_deleting_referenced_menu_item_returns_409_not_500(client, vendor_auth_headers):
    child = client.post("/menu-items", json={
        "name": "Basmati Peas Pilaf", "course": "main", "vegNonveg": "veg", "priceWeight": "standard",
    }, headers=vendor_auth_headers).json()
    parent = client.post("/menu-items", json={
        "name": "Basmati Pilaf", "course": "main", "vegNonveg": "veg", "priceWeight": "standard",
    }, headers=vendor_auth_headers).json()
    client.post(
        "/item-relationships", json={"childId": child["id"], "parentId": parent["id"]}, headers=vendor_auth_headers
    )

    # parent is still referenced by the edge above — deleting it must fail
    # cleanly (409), not leak a raw IntegrityError as a 500
    resp = client.delete(f"/menu-items/{parent['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 409
    assert "detail" in resp.json()

    # and it must genuinely still exist afterward — the failed delete
    # should not have partially applied
    assert client.get(f"/menu-items/{parent['id']}", headers=vendor_auth_headers).status_code == 200


def test_duplicate_menu_item_name_returns_409(client, vendor_auth_headers):
    body = {"name": "Unique Dish", "course": "main", "vegNonveg": "veg", "priceWeight": "standard"}
    first = client.post("/menu-items", json=body, headers=vendor_auth_headers)
    assert first.status_code == 200

    second = client.post("/menu-items", json=body, headers=vendor_auth_headers)
    assert second.status_code == 409
