import uuid

import pytest


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
    resp = client.get(f"/menu-items/{uuid.uuid4()}", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_get_menu_item_with_malformed_id_returns_422(client, vendor_auth_headers):
    resp = client.get("/menu-items/does-not-exist", headers=vendor_auth_headers)
    assert resp.status_code == 422


def test_update_menu_item(client, test_menu_item, vendor_auth_headers):
    resp = client.patch(
        f"/menu-items/{test_menu_item['id']}", json={"active": False}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["active"] is False
    assert resp.json()["name"] == test_menu_item["name"]

    # read back in a new request: the PATCH response alone would look right
    # even if the route never committed
    resp = client.get(f"/menu-items/{test_menu_item['id']}", headers=vendor_auth_headers)
    assert resp.json()["active"] is False


def test_delete_menu_item(client, test_menu_item, vendor_auth_headers):
    resp = client.delete(f"/menu-items/{test_menu_item['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/menu-items/{test_menu_item['id']}", headers=vendor_auth_headers).status_code == 404


def _menu_item_body(**overrides):
    return {
        "name": "Paneer Tikka",
        "course": "appetizer",
        "vegNonveg": "veg",
        "priceWeight": "standard",
        **overrides,
    }


def test_cost_per_person_is_exact_and_sent_as_a_number(client, vendor_auth_headers):
    # stored exactly as a Decimal, sent to the frontend as a plain JSON number
    resp = client.post(
        "/menu-items", json=_menu_item_body(costPerPerson="12.10"), headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["costPerPerson"] == 12.10


def test_cost_per_person_accepts_a_json_number(client, vendor_auth_headers):
    resp = client.post(
        "/menu-items", json=_menu_item_body(costPerPerson=12.5), headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["costPerPerson"] == 12.50


def test_cost_per_person_can_be_left_out(client, vendor_auth_headers):
    resp = client.post("/menu-items", json=_menu_item_body(), headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["costPerPerson"] is None


def test_cost_per_person_can_be_zero(client, vendor_auth_headers):
    resp = client.post(
        "/menu-items", json=_menu_item_body(costPerPerson="0"), headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("bad_cost", [
    "-1",          # negative
    "12.345",      # more than 2 decimal places: the column would round it
    "1234567.00",  # more than 8 digits: the column would overflow
])
def test_invalid_cost_per_person_rejected_on_create(client, vendor_auth_headers, bad_cost):
    resp = client.post(
        "/menu-items", json=_menu_item_body(costPerPerson=bad_cost), headers=vendor_auth_headers
    )
    assert resp.status_code == 422, resp.text


def test_update_cost_per_person(client, test_menu_item, vendor_auth_headers):
    resp = client.patch(
        f"/menu-items/{test_menu_item['id']}", json={"costPerPerson": "18.75"}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["costPerPerson"] == 18.75


@pytest.mark.parametrize("bad_cost", ["-1", "12.345", "1234567.00"])
def test_invalid_cost_per_person_rejected_on_update(client, test_menu_item, vendor_auth_headers, bad_cost):
    resp = client.patch(
        f"/menu-items/{test_menu_item['id']}", json={"costPerPerson": bad_cost}, headers=vendor_auth_headers
    )
    assert resp.status_code == 422, resp.text
