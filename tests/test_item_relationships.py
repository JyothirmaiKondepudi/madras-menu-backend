import uuid


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


def test_update_edge_moves_child_to_new_parent(client, vendor_auth_headers):
    child = _make_item(client, "Mint Pilaf", vendor_auth_headers)
    first_parent = _make_item(client, "Pilaf", vendor_auth_headers)
    new_parent = _make_item(client, "Rice Dish", vendor_auth_headers)
    client.post("/item-relationships", json={
        "childId": child["id"], "parentId": first_parent["id"],
    }, headers=vendor_auth_headers)

    resp = client.patch(f"/item-relationships/{child['id']}", json={
        "newParentId": new_parent["id"], "reason": "broader parent",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["toItemId"] == new_parent["id"]

    # read back in a new request: the PATCH response alone would look right
    # even if the route never committed
    resp = client.get(f"/item-relationships/{child['id']}", headers=vendor_auth_headers)
    assert resp.json()["toItemId"] == new_parent["id"]


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
    resp = client.get(f"/item-relationships/{uuid.uuid4()}", headers=vendor_auth_headers)
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

    # delete_node only removes it from the hierarchy, not the dish itself
    assert client.get(f"/menu-items/{parent['id']}", headers=vendor_auth_headers).status_code == 200


# --- BE-28: the hierarchy can't be corrupted ---------------------------------


def _link(client, child, parent, headers):
    return client.post("/item-relationships", json={"childId": child["id"], "parentId": parent["id"]}, headers=headers)


def test_simultaneous_opposite_links_cant_create_a_loop(client, engine, vendor_auth_headers):
    """A under B and B under A at the same moment: without the lock both pass
    the loop check and the tree ends up with A -> B -> A. With it, the second
    waits for the first to commit, sees its edge and is refused."""
    import threading
    from uuid import UUID

    from sqlalchemy.orm import Session

    from hierarchy.mutations import HierarchyError, insert_edge

    a = UUID(_make_item(client, "Dish A", vendor_auth_headers)["id"])
    b = UUID(_make_item(client, "Dish B", vendor_auth_headers)["id"])
    outcome = {}

    def second():
        with Session(engine) as db:
            try:
                insert_edge(db, child_id=b, parent_id=a)
                db.commit()
                outcome["second"] = "linked"
            except HierarchyError as exc:
                outcome["second"] = str(exc)

    with Session(engine) as first:
        insert_edge(first, child_id=a, parent_id=b)  # holds the lock until commit
        thread = threading.Thread(target=second)
        thread.start()
        thread.join(timeout=1)
        waited = thread.is_alive()
        first.commit()
    thread.join(timeout=10)

    assert waited, "the second change didn't wait for the first"
    assert "cycle" in outcome["second"]
    edges = client.get("/item-relationships", headers=vendor_auth_headers).json()["items"]
    assert [(e["fromItemId"], e["toItemId"]) for e in edges] == [(str(a), str(b))]


def test_loop_several_levels_up_is_refused(client, vendor_auth_headers):
    # rice <- pilaf <- peas pilaf <- garden peas pilaf; now rice under the deepest one
    names = ["Rice", "Pilaf", "Peas Pilaf", "Garden Peas Pilaf"]
    items = [_make_item(client, n, vendor_auth_headers) for n in names]
    for parent, child in zip(items, items[1:]):
        assert _link(client, child, parent, vendor_auth_headers).status_code == 200

    resp = _link(client, items[0], items[-1], vendor_auth_headers)
    assert resp.status_code == 400
    assert "cycle" in resp.json()["detail"]

    # the same via reclassifying
    resp = client.patch(f"/item-relationships/{items[1]['id']}",
                        json={"newParentId": items[3]["id"]}, headers=vendor_auth_headers)
    assert resp.status_code == 400


def test_failed_reclassify_leaves_the_old_parent(client, vendor_auth_headers):
    # a refused reclassify changes nothing: the child keeps its old parent
    parent = _make_item(client, "Biryani", vendor_auth_headers)
    child = _make_item(client, "Veg Biryani", vendor_auth_headers)
    _link(client, child, parent, vendor_auth_headers)

    resp = client.patch(f"/item-relationships/{parent['id']}", json={"newParentId": child["id"]},
                        headers=vendor_auth_headers)
    assert resp.status_code == 400
    edge = client.get(f"/item-relationships/{child['id']}", headers=vendor_auth_headers).json()
    assert edge["toItemId"] == parent["id"]


def test_reclassify_keeps_the_edge_id(client, vendor_auth_headers):
    child = _make_item(client, "Lemon Rice", vendor_auth_headers)
    first, second = (_make_item(client, n, vendor_auth_headers) for n in ("Rice", "South Indian Rice"))
    created = _link(client, child, first, vendor_auth_headers).json()
    moved = client.patch(f"/item-relationships/{child['id']}", json={"newParentId": second["id"]},
                         headers=vendor_auth_headers).json()
    assert moved["id"] == created["id"]


def test_unknown_relationship_type_is_rejected(client, vendor_auth_headers):
    child, parent = (_make_item(client, n, vendor_auth_headers) for n in ("Dosa", "Crepe"))
    resp = client.post("/item-relationships", json={
        "childId": child["id"], "parentId": parent["id"], "relationshipType": "pairs_with",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 422
    resp = client.delete(f"/item-relationships/{child['id']}?relationship_type=pairs_with", headers=vendor_auth_headers)
    assert resp.status_code == 422


def test_database_rejects_own_parent_and_unknown_type(client, engine, vendor_auth_headers):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    item = _make_item(client, "Idli", vendor_auth_headers)
    other = _make_item(client, "Steamed Cake", vendor_auth_headers)
    sql = text("INSERT INTO item_relationships (id, from_item_id, to_item_id, relationship_type) "
               "VALUES (gen_random_uuid(), :c, :p, :t)")
    with pytest.raises(IntegrityError, match="not_own_parent_check"):
        with engine.begin() as conn:
            conn.execute(sql, {"c": item["id"], "p": item["id"], "t": "parent_of"})
    with pytest.raises(IntegrityError, match="relationship_type_check"):
        with engine.begin() as conn:
            conn.execute(sql, {"c": item["id"], "p": other["id"], "t": "pairs_with"})
