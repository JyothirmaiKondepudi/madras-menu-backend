def _make_item(client, name, headers):
    return client.post("/menu-items", json={
        "name": name, "course": "main", "vegNonveg": "veg", "priceWeight": "standard",
    }, headers=headers).json()


def test_create_edge(client, vendor_auth_headers):
    child = _make_item(client, "Basmati Peas Pilaf", vendor_auth_headers)
    parent = _make_item(client, "Basmati Pilaf", vendor_auth_headers)

    resp = client.post("/item-relationships", json={
        "childId": child["id"], "parentId": parent["id"], "reason": "peas variant",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["fromItemId"] == child["id"]
    assert resp.json()["toItemId"] == parent["id"]


def test_item_relationships_require_vendor(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/item-relationships", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_self_parent_rejected(client, vendor_auth_headers):
    item = _make_item(client, "Basmati Pilaf", vendor_auth_headers)
    resp = client.post(
        "/item-relationships", json={"childId": item["id"], "parentId": item["id"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 400
    assert "own parent" in resp.json()["detail"]


def test_cycle_rejected(client, vendor_auth_headers):
    a = _make_item(client, "Dish A", vendor_auth_headers)
    b = _make_item(client, "Dish B", vendor_auth_headers)

    # a -> b (b is a's parent)
    first = client.post(
        "/item-relationships", json={"childId": a["id"], "parentId": b["id"]}, headers=vendor_auth_headers
    )
    assert first.status_code == 200, first.text

    # b -> a would close a cycle (a -> b -> a)
    second = client.post(
        "/item-relationships", json={"childId": b["id"], "parentId": a["id"]}, headers=vendor_auth_headers
    )
    assert second.status_code == 400
    assert "cycle" in second.json()["detail"]


def test_get_edge_by_child_id(client, vendor_auth_headers):
    child = _make_item(client, "Child Dish", vendor_auth_headers)
    parent = _make_item(client, "Parent Dish", vendor_auth_headers)
    client.post(
        "/item-relationships",
        json={"childId": child["id"], "parentId": parent["id"]},
        headers=vendor_auth_headers,
    )

    resp = client.get(f"/item-relationships/{child['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["toItemId"] == parent["id"]


def test_get_nonexistent_edge_returns_404(client, vendor_auth_headers):
    resp = client.get("/item-relationships/does-not-exist", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_delete_edge(client, vendor_auth_headers):
    child = _make_item(client, "Child Dish", vendor_auth_headers)
    parent = _make_item(client, "Parent Dish", vendor_auth_headers)
    client.post(
        "/item-relationships",
        json={"childId": child["id"], "parentId": parent["id"]},
        headers=vendor_auth_headers,
    )

    resp = client.delete(f"/item-relationships/{child['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/item-relationships/{child['id']}", headers=vendor_auth_headers).status_code == 404


def test_delete_node_reparents_children(client, vendor_auth_headers):
    grandparent = _make_item(client, "Basmati rice", vendor_auth_headers)
    parent = _make_item(client, "Basmati Pilaf", vendor_auth_headers)
    child = _make_item(client, "Basmati Peas Pilaf", vendor_auth_headers)

    client.post(
        "/item-relationships",
        json={"childId": parent["id"], "parentId": grandparent["id"]},
        headers=vendor_auth_headers,
    )
    client.post(
        "/item-relationships",
        json={"childId": child["id"], "parentId": parent["id"]},
        headers=vendor_auth_headers,
    )

    resp = client.delete(f"/item-relationships/nodes/{parent['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["reparented_children"] == [child["id"]]

    # child should now point directly at grandparent, one level up
    edge = client.get(f"/item-relationships/{child['id']}", headers=vendor_auth_headers)
    assert edge.json()["toItemId"] == grandparent["id"]

    # the deleted node's own menu_items row should still exist (delete_node
    # only removes it from the hierarchy, never the dish itself)
    assert client.get(f"/menu-items/{parent['id']}", headers=vendor_auth_headers).status_code == 200
