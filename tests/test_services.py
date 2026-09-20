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


def test_create_service(client, test_project, admin_auth_headers):
    resp = client.post("/services", json=_service_body(test_project["projectId"]), headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["serviceName"] == "Wedding Reception Dinner"
    assert resp.json()["cuisine"] == ["South Indian", "North Indian"]


def test_create_service_requires_admin(client, test_project, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/services",
        json=_service_body(test_project["projectId"]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_service_includes_nested_project_and_client(client, test_project, admin_auth_headers):
    created = client.post(
        "/services", json=_service_body(test_project["projectId"]), headers=admin_auth_headers
    ).json()

    resp = client.get(f"/services/{created['serviceId']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["project"]["projectId"] == test_project["projectId"]
    assert body["project"]["client"]["userId"] == test_project["clientId"]


def test_get_services_by_project_id(client, test_project, admin_auth_headers):
    created = client.post(
        "/services", json=_service_body(test_project["projectId"]), headers=admin_auth_headers
    ).json()

    resp = client.get(f"/services/projects/{test_project['projectId']}", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert any(s["serviceId"] == created["serviceId"] for s in resp.json())


def test_get_nonexistent_service_returns_404(client, admin_auth_headers):
    resp = client.get("/services/00000000-0000-0000-0000-000000000000", headers=admin_auth_headers)
    assert resp.status_code == 404


def test_get_services_requires_auth(client):
    assert client.get("/services").status_code == 401


def test_client_only_sees_services_for_linked_projects(client, test_project, test_client_login, admin_auth_headers):
    client.post("/services", json=_service_body(test_project["projectId"]), headers=admin_auth_headers)
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/services", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []

    client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=admin_auth_headers,
    )
    resp = client.get("/services", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 1
