import uuid

import pytest


def test_create_tax_category(client, vendor_auth_headers):
    resp = client.post("/tax-categories", json={
        "name": "prepared_food",
        "jurisdiction": "FL",
        "ratePercent": 7.0,
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "prepared_food"


def test_tax_categories_require_vendor(client, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/tax-categories", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_tax_category_by_id(client, vendor_auth_headers):
    created = client.post("/tax-categories", json={
        "name": "alcohol", "jurisdiction": "FL", "ratePercent": 7.0,
    }, headers=vendor_auth_headers).json()

    resp = client.get(f"/tax-categories/{created['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_nonexistent_tax_category_returns_404(client, vendor_auth_headers):
    resp = client.get(f"/tax-categories/{uuid.uuid4()}", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_get_tax_category_with_malformed_id_returns_422(client, vendor_auth_headers):
    resp = client.get("/tax-categories/does-not-exist", headers=vendor_auth_headers)
    assert resp.status_code == 422


def test_delete_tax_category(client, vendor_auth_headers):
    created = client.post("/tax-categories", json={
        "name": "service_labor", "jurisdiction": "FL", "ratePercent": 0.0,
    }, headers=vendor_auth_headers).json()

    resp = client.delete(f"/tax-categories/{created['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/tax-categories/{created['id']}", headers=vendor_auth_headers).status_code == 404


def _tax_body(**overrides):
    return {"name": "prepared_food", "jurisdiction": "FL", "ratePercent": "7.000", **overrides}


def test_rate_percent_is_exact_and_sent_as_a_number(client, vendor_auth_headers):
    resp = client.post("/tax-categories", json=_tax_body(ratePercent="7.125"), headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ratePercent"] == 7.125


@pytest.mark.parametrize("bad_rate", [
    "-1",       # negative
    "100.001",  # over 100%
    "7.1234",   # more than 3 decimal places: the column would round it
])
def test_invalid_rate_percent_rejected_on_create(client, vendor_auth_headers, bad_rate):
    resp = client.post("/tax-categories", json=_tax_body(ratePercent=bad_rate), headers=vendor_auth_headers)
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("bad_rate", ["-1", "100.001", "7.1234"])
def test_invalid_rate_percent_rejected_on_update(client, vendor_auth_headers, bad_rate):
    created = client.post("/tax-categories", json=_tax_body(), headers=vendor_auth_headers).json()
    resp = client.patch(
        f"/tax-categories/{created['id']}", json={"ratePercent": bad_rate}, headers=vendor_auth_headers
    )
    assert resp.status_code == 422, resp.text


def test_update_without_rate_keeps_it(client, vendor_auth_headers):
    # ratePercent is optional on update: renaming must not require resending it
    created = client.post(
        "/tax-categories", json=_tax_body(ratePercent="7.125"), headers=vendor_auth_headers
    ).json()
    resp = client.patch(
        f"/tax-categories/{created['id']}", json={"name": "renamed"}, headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "renamed"
    assert resp.json()["ratePercent"] == 7.125


def test_update_rejects_null_rate(client, vendor_auth_headers):
    # the column is NOT NULL: an explicit null is a 422, not a database error
    created = client.post("/tax-categories", json=_tax_body(), headers=vendor_auth_headers).json()
    resp = client.patch(
        f"/tax-categories/{created['id']}", json={"ratePercent": None}, headers=vendor_auth_headers
    )
    assert resp.status_code == 422, resp.text
