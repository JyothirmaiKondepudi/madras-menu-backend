def test_create_invoice(client, test_user):
    resp = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 2500.0,
        "invoiceAssignedTo": test_user["userId"],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAmount"] == 2500.0


def test_get_invoice_by_id(client, test_user):
    created = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": test_user["userId"],
    }).json()

    resp = client.get(f"/invoices/{created['invoiceId']}")
    assert resp.status_code == 200
    assert resp.json()["invoiceId"] == created["invoiceId"]


def test_get_nonexistent_invoice_returns_404(client):
    resp = client.get("/invoices/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_update_invoice(client, test_user):
    created = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": test_user["userId"],
    }).json()

    resp = client.patch(f"/invoices/{created['invoiceId']}", json={"invoiceStatus": "Paid"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Paid"


def test_delete_invoice(client, test_user):
    created = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "invoiceAmount": 100.0,
        "invoiceAssignedTo": test_user["userId"],
    }).json()

    resp = client.delete(f"/invoices/{created['invoiceId']}")
    assert resp.status_code == 204
    assert client.get(f"/invoices/{created['invoiceId']}").status_code == 404
