"""Each caterer has its own dish catalog: dishes, their family links and dish
search never cross organizations."""
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

DISH = {"course": "main", "vegNonveg": "veg", "priceWeight": "standard"}


def _dish(client, name, headers, **extra):
    resp = client.post("/menu-items", json={"name": name, **DISH, **extra}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_another_org_cant_see_or_change_dishes(client, vendor_auth_headers, other_vendor):
    dish = _dish(client, "Paneer Tikka", vendor_auth_headers)
    path = f"/menu-items/{dish['id']}"

    assert client.get("/menu-items", headers=other_vendor).json()["total"] == 0
    assert client.get(path, headers=other_vendor).status_code == 404
    assert client.patch(path, json={"name": "Taken"}, headers=other_vendor).status_code == 404
    assert client.delete(path, headers=other_vendor).status_code == 404
    # untouched for its owner
    assert client.get(path, headers=vendor_auth_headers).json()["name"] == "Paneer Tikka"


def test_names_are_unique_per_caterer(client, vendor_auth_headers, other_vendor):
    _dish(client, "Dal Makhani", vendor_auth_headers)
    _dish(client, "Dal Makhani", other_vendor)  # another caterer may use the same name
    resp = client.post("/menu-items", json={"name": "Dal Makhani", **DISH}, headers=vendor_auth_headers)
    assert resp.status_code == 409


def test_a_dish_goes_to_the_callers_org_whatever_the_body_says(
    client, engine, vendor_auth_headers, other_vendor, test_vendor_login
):
    other_org = client.get("/auth/me", headers=other_vendor).json()["userOrg"]
    dish = client.post(
        "/menu-items", json={"name": "Sneaky", **DISH, "orgId": other_org}, headers=vendor_auth_headers
    ).json()
    with engine.connect() as conn:
        owner = conn.execute(text("SELECT org_id FROM menu_items WHERE id = :id"), {"id": dish["id"]}).scalar()
    assert str(owner) == test_vendor_login["userOrg"]


def test_family_links_stay_inside_one_caterer(client, vendor_auth_headers, other_vendor):
    mine = _dish(client, "Chicken Biryani", vendor_auth_headers)
    theirs = _dish(client, "Biryani", other_vendor)

    resp = client.post(
        "/item-relationships", json={"childId": mine["id"], "parentId": theirs["id"]}, headers=vendor_auth_headers
    )
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]

    parent = _dish(client, "Biryani", vendor_auth_headers)
    linked = client.post(
        "/item-relationships", json={"childId": mine["id"], "parentId": parent["id"]}, headers=vendor_auth_headers
    )
    assert linked.status_code == 200, linked.text
    # the other caterer sees none of it, and can't change it
    assert client.get("/item-relationships", headers=other_vendor).json()["total"] == 0
    assert client.get(f"/item-relationships/{mine['id']}", headers=other_vendor).status_code == 404
    assert client.delete(f"/item-relationships/{mine['id']}", headers=other_vendor).status_code == 404
    assert client.delete(f"/item-relationships/nodes/{parent['id']}", headers=other_vendor).status_code == 400
    assert client.get(f"/item-relationships/{mine['id']}", headers=vendor_auth_headers).status_code == 200


def test_database_refuses_a_link_between_two_caterers(
    client, engine, vendor_auth_headers, other_vendor, test_vendor_login
):
    mine = _dish(client, "Masala Dosa", vendor_auth_headers)
    theirs = _dish(client, "Dosa", other_vendor)
    with pytest.raises(IntegrityError, match="item_relationships_to_item_org_fkey"):
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO item_relationships (id, org_id, from_item_id, to_item_id, relationship_type) "
                     "VALUES (gen_random_uuid(), :o, :c, :p, 'parent_of')"),
                {"o": test_vendor_login["userOrg"], "c": mine["id"], "p": theirs["id"]},
            )


def test_embeddings_and_search_stay_inside_one_caterer(client, vendor_auth_headers, other_vendor):
    mine = _dish(client, "Tamarind Rice", vendor_auth_headers)
    theirs = _dish(client, "Puliogare", other_vendor)
    vector = [0.1] * 768
    with patch("embeddings.service.generate_embedding", return_value=vector):
        assert client.post(f"/menu-items/{theirs['id']}/embedding", headers=vendor_auth_headers).status_code == 404
        assert client.post(f"/menu-items/{mine['id']}/embedding", headers=vendor_auth_headers).status_code == 200
        assert client.post(f"/menu-items/{theirs['id']}/embedding", headers=other_vendor).status_code == 200

        found = client.get("/embeddings/search", params={"text": "tamarind rice"}, headers=vendor_auth_headers)
        assert [r["name"] for r in found.json()] == ["Tamarind Rice"]
        found = client.get("/embeddings/search", params={"text": "tamarind rice"}, headers=other_vendor)
        assert [r["name"] for r in found.json()] == ["Puliogare"]
