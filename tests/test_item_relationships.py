def _make_item(client, name):
    return client.post("/menu-items", json={
        "name": name, "course": "main", "vegNonveg": "veg", "priceWeight": "standard",
    }).json()


def test_create_edge(client):
    child = _make_item(client, "Basmati Peas Pilaf")
    parent = _make_item(client, "Basmati Pilaf")

    resp = client.post("/item-relationships", json={
        "childId": child["id"], "parentId": parent["id"], "reason": "peas variant",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["fromItemId"] == child["id"]
    assert resp.json()["toItemId"] == parent["id"]


def test_self_parent_rejected(client):
    item = _make_item(client, "Basmati Pilaf")
    resp = client.post("/item-relationships", json={"childId": item["id"], "parentId": item["id"]})
    assert resp.status_code == 400
    assert "own parent" in resp.json()["detail"]


def test_cycle_rejected(client):
    a = _make_item(client, "Dish A")
    b = _make_item(client, "Dish B")

    # a -> b (b is a's parent)
    first = client.post("/item-relationships", json={"childId": a["id"], "parentId": b["id"]})
    assert first.status_code == 200, first.text

    # b -> a would close a cycle (a -> b -> a)
    second = client.post("/item-relationships", json={"childId": b["id"], "parentId": a["id"]})
    assert second.status_code == 400
    assert "cycle" in second.json()["detail"]


def test_get_edge_by_child_id(client):
    child = _make_item(client, "Child Dish")
    parent = _make_item(client, "Parent Dish")
    client.post("/item-relationships", json={"childId": child["id"], "parentId": parent["id"]})

    resp = client.get(f"/item-relationships/{child['id']}")
    assert resp.status_code == 200
    assert resp.json()["toItemId"] == parent["id"]


def test_get_nonexistent_edge_returns_404(client):
    resp = client.get("/item-relationships/does-not-exist")
    assert resp.status_code == 404


def test_delete_edge(client):
    child = _make_item(client, "Child Dish")
    parent = _make_item(client, "Parent Dish")
    client.post("/item-relationships", json={"childId": child["id"], "parentId": parent["id"]})

    resp = client.delete(f"/item-relationships/{child['id']}")
    assert resp.status_code == 204
    assert client.get(f"/item-relationships/{child['id']}").status_code == 404


def test_delete_node_reparents_children(client):
    grandparent = _make_item(client, "Basmati rice")
    parent = _make_item(client, "Basmati Pilaf")
    child = _make_item(client, "Basmati Peas Pilaf")

    client.post("/item-relationships", json={"childId": parent["id"], "parentId": grandparent["id"]})
    client.post("/item-relationships", json={"childId": child["id"], "parentId": parent["id"]})

    resp = client.delete(f"/item-relationships/nodes/{parent['id']}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["reparented_children"] == [child["id"]]

    # child should now point directly at grandparent, one level up
    edge = client.get(f"/item-relationships/{child['id']}")
    assert edge.json()["toItemId"] == grandparent["id"]

    # the deleted node's own menu_items row should still exist (delete_node
    # only removes it from the hierarchy, never the dish itself)
    assert client.get(f"/menu-items/{parent['id']}").status_code == 200
