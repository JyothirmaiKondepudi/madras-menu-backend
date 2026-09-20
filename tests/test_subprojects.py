def _subproject_body(project_id):
    return {
        "subprojectName": "Wedding Reception Dinner",
        "projectAssociatedTo": project_id,
        "cuisine": ["South Indian", "North Indian"],
        "religion": "Hindu",
        "subprojectDate": "2026-11-14T19:00:00",
        "guestCount": 150,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
        "minPricePerPerson": 45.0,
        "maxPricePerPerson": 65.0,
    }


def test_create_subproject(client, test_project, vendor_auth_headers):
    resp = client.post("/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["subprojectName"] == "Wedding Reception Dinner"
    assert resp.json()["cuisine"] == ["South Indian", "North Indian"]


def test_create_subproject_requires_vendor(client, test_project, test_client_login):
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_subproject_includes_nested_project_and_client(client, test_project, vendor_auth_headers):
    created = client.post(
        "/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers
    ).json()

    resp = client.get(f"/subprojects/{created['subprojectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["project"]["projectId"] == test_project["projectId"]
    assert body["project"]["client"]["userId"] == test_project["clientId"]


def test_get_subprojects_by_project_id(client, test_project, vendor_auth_headers):
    created = client.post(
        "/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers
    ).json()

    resp = client.get(f"/subprojects/projects/{test_project['projectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert any(s["subprojectId"] == created["subprojectId"] for s in resp.json())


def test_get_nonexistent_subproject_returns_404(client, vendor_auth_headers):
    resp = client.get("/subprojects/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_get_subprojects_requires_auth(client):
    assert client.get("/subprojects").status_code == 401


def test_client_only_sees_subprojects_for_linked_projects(client, test_project, test_client_login, vendor_auth_headers):
    client.post("/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers)
    login_resp = client.post("/auth/login", json={
        "email": test_client_login["userEmail"],
        "password": "correct-horse-battery-staple",
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/subprojects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []

    client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )
    resp = client.get("/subprojects", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 1
