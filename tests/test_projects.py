def test_create_project(client, test_user):
    resp = client.post("/projects", json={
        "projectName": "Wedding Reception",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "adminOnProject": test_user["userId"],
        "clientId": test_user["userId"],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["projectName"] == "Wedding Reception"


def test_get_project_includes_nested_client_and_admin(client, test_project):
    resp = client.get(f"/projects/{test_project['projectId']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["client"]["userId"] == test_project["clientId"]
    assert body["admin"]["userId"] == test_project["adminOnProject"]


def test_get_nonexistent_project_returns_404(client):
    resp = client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_get_projects_by_user_id(client, test_project):
    resp = client.get(f"/projects/users/{test_project['clientId']}")
    assert resp.status_code == 200
    assert any(p["projectId"] == test_project["projectId"] for p in resp.json())


def test_delete_project(client, test_project):
    resp = client.delete(f"/projects/{test_project['projectId']}")
    assert resp.status_code == 204
    assert client.get(f"/projects/{test_project['projectId']}").status_code == 404


def test_partial_update_project(client, test_project):
    """A PATCH should only require the field(s) actually being changed."""
    resp = client.patch(
        f"/projects/{test_project['projectId']}", json={"projectName": "Renamed Project"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["projectName"] == "Renamed Project"
    # untouched fields survive
    assert resp.json()["projectStatus"] == test_project["projectStatus"]
