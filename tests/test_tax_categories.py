def test_create_tax_category(client):
    resp = client.post("/tax-categories", json={
        "name": "prepared_food",
        "jurisdiction": "FL",
        "ratePercent": 7.0,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "prepared_food"


def test_get_tax_category_by_id(client):
    created = client.post("/tax-categories", json={
        "name": "alcohol", "jurisdiction": "FL", "ratePercent": 7.0,
    }).json()

    resp = client.get(f"/tax-categories/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_nonexistent_tax_category_returns_404(client):
    resp = client.get("/tax-categories/does-not-exist")
    assert resp.status_code == 404


def test_delete_tax_category(client):
    created = client.post("/tax-categories", json={
        "name": "service_labor", "jurisdiction": "FL", "ratePercent": 0.0,
    }).json()

    resp = client.delete(f"/tax-categories/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/tax-categories/{created['id']}").status_code == 404
