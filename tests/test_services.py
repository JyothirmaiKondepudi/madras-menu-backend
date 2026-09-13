def _service_body(project_id):
    return {
        "serviceName": "Wedding Reception Dinner",
        "projectAssociatedTo": project_id,
        "cuisine": ["South Indian", "North Indian"],
        "religion": "Hindu",
        "serviceDate": "2026-11-14T19:00:00",
        "guestCount": 150,
        "serviceType": "Buffet",
        "serviceVenue": "Hotel",
        "serviceEvent": "Wedding Dinner",
        "minPricePerPerson": 45.0,
        "maxPricePerPerson": 65.0,
    }


def test_create_service(client, test_project):
    resp = client.post("/services", json=_service_body(test_project["projectId"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["serviceName"] == "Wedding Reception Dinner"
    assert resp.json()["cuisine"] == ["South Indian", "North Indian"]


def test_get_service_includes_nested_project_and_client(client, test_project):
    created = client.post("/services", json=_service_body(test_project["projectId"])).json()

    resp = client.get(f"/services/{created['serviceId']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project"]["projectId"] == test_project["projectId"]
    assert body["project"]["client"]["userId"] == test_project["clientId"]


def test_get_services_by_project_id(client, test_project):
    created = client.post("/services", json=_service_body(test_project["projectId"])).json()

    resp = client.get(f"/services/projects/{test_project['projectId']}")
    assert resp.status_code == 200
    assert any(s["serviceId"] == created["serviceId"] for s in resp.json())


def test_get_nonexistent_service_returns_404(client):
    resp = client.get("/services/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
