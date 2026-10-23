"""BE-08b: ?include=subprojects,invoices,billing on project responses."""
from sqlalchemy import event

ALL = "subprojects,invoices,billing"


def _project(client, vendor_id, headers, name="Wedding"):
    return client.post("/projects", json={
        "projectName": name,
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": vendor_id,
    }, headers=headers).json()


def _event(client, project_id, headers, date="2026-11-14T19:00:00"):
    return client.post("/subprojects", json={
        "subprojectName": "Reception",
        "projectAssociatedTo": project_id,
        "subprojectDate": date,
        "guestCount": 100,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
    }, headers=headers).json()


def _invoice(client, project_id, user_id, headers, subproject_id=None):
    body = {"totalAmount": 1000.0, "depositPercentage": 100,
            "invoiceAssignedTo": user_id, "projectAssociatedTo": project_id}
    if subproject_id:
        body["subprojectId"] = subproject_id
    resp = client.post("/invoices", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _link(client, project_id, user_id, headers):
    client.post(f"/projects/{project_id}/users/{user_id}", headers=headers)


def _login(client, email):
    token = client.post("/auth/login", json={
        "email": email, "password": "correct-horse-battery-staple",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_without_include_the_extra_fields_are_null(client, test_project, vendor_auth_headers):
    [project] = client.get("/projects", headers=vendor_auth_headers).json()["items"]
    assert project["subprojects"] is None
    assert project["invoices"] is None
    assert project["billing"] is None


def test_include_everything(client, test_user, test_project, vendor_auth_headers):
    pid = test_project["projectId"]
    event_ = _event(client, pid, vendor_auth_headers)
    on_event = _invoice(client, pid, test_user["userId"], vendor_auth_headers, event_["subprojectId"])
    deposit = _invoice(client, pid, test_user["userId"], vendor_auth_headers)
    client.post(f"/invoices/{on_event['invoiceId']}/accept", headers=vendor_auth_headers)

    [project] = client.get(f"/projects?include={ALL}", headers=vendor_auth_headers).json()["items"]
    assert [s["subprojectId"] for s in project["subprojects"]] == [event_["subprojectId"]]
    assert {i["invoiceId"] for i in project["invoices"]} == {on_event["invoiceId"], deposit["invoiceId"]}
    # per-event billing only: the project-level deposit has no summary
    [billing] = project["billing"]
    assert billing["subprojectId"] == event_["subprojectId"]
    assert billing["totalInvoiced"] == 1000.0
    # nested items don't repeat the project they're inside
    assert "project" not in project["subprojects"][0]
    assert "project" not in project["invoices"][0]


def test_requested_but_empty_is_an_empty_list(client, test_project, vendor_auth_headers):
    [project] = client.get("/projects?include=subprojects,invoices", headers=vendor_auth_headers).json()["items"]
    assert project["subprojects"] == []
    assert project["invoices"] == []
    assert project["billing"] is None  # not requested


def test_unknown_include_is_rejected(client, test_project, vendor_auth_headers):
    resp = client.get("/projects?include=subprojects,menus", headers=vendor_auth_headers)
    assert resp.status_code == 422
    assert "menus" in resp.json()["detail"]


def test_include_on_single_project_and_user_projects(client, test_user, test_project, vendor_auth_headers):
    pid = test_project["projectId"]
    _event(client, pid, vendor_auth_headers)

    one = client.get(f"/projects/{pid}?include=subprojects", headers=vendor_auth_headers).json()
    assert len(one["subprojects"]) == 1

    page = client.get(f"/users/{test_user['userId']}/projects?include=subprojects",
                      headers=vendor_auth_headers).json()
    [same] = [p for p in page["items"] if p["projectId"] == pid]
    assert len(same["subprojects"]) == 1


def test_deleted_invoices_are_not_included(client, test_user, test_project, vendor_auth_headers):
    pid = test_project["projectId"]
    kept = _invoice(client, pid, test_user["userId"], vendor_auth_headers)
    gone = _invoice(client, pid, test_user["userId"], vendor_auth_headers)
    client.delete(f"/invoices/{gone['invoiceId']}", headers=vendor_auth_headers)

    project = client.get(f"/projects/{pid}?include=invoices", headers=vendor_auth_headers).json()
    assert [i["invoiceId"] for i in project["invoices"]] == [kept["invoiceId"]]


def test_client_only_gets_invoices_billed_to_them(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    # two clients on the project, one invoice each: like GET /invoices, a
    # client sees only their own
    pid = test_project["projectId"]
    _link(client, pid, test_client_login["userId"], vendor_auth_headers)
    mine = _invoice(client, pid, test_client_login["userId"], vendor_auth_headers)
    _invoice(client, pid, test_user["userId"], vendor_auth_headers)

    client_auth = _login(client, test_client_login["userEmail"])
    project = client.get(f"/projects/{pid}?include=invoices", headers=client_auth).json()
    assert [i["invoiceId"] for i in project["invoices"]] == [mine["invoiceId"]]

    vendor_view = client.get(f"/projects/{pid}?include=invoices", headers=vendor_auth_headers).json()
    assert len(vendor_view["invoices"]) == 2


def test_query_count_does_not_grow_with_the_number_of_projects(
    client, engine, test_user, vendor_auth_headers
):
    def queries_for_page():
        statements = []

        def count(*args):
            statements.append(1)

        event.listen(engine, "before_cursor_execute", count)
        try:
            resp = client.get(f"/projects?include={ALL}", headers=vendor_auth_headers)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        assert resp.status_code == 200, resp.text
        return len(statements)

    def add_project_with_data(name):
        project = _project(client, test_user["userId"], vendor_auth_headers, name)
        _link(client, project["projectId"], test_user["userId"], vendor_auth_headers)
        event_ = _event(client, project["projectId"], vendor_auth_headers)
        invoice = _invoice(client, project["projectId"], test_user["userId"], vendor_auth_headers,
                           event_["subprojectId"])
        client.post(f"/invoices/{invoice['invoiceId']}/accept", headers=vendor_auth_headers)

    add_project_with_data("One")
    client.get(f"/projects?include={ALL}", headers=vendor_auth_headers)  # warm the permission cache
    with_one = queries_for_page()
    for name in ("Two", "Three", "Four"):
        add_project_with_data(name)
    with_four = queries_for_page()
    assert with_four == with_one, (with_one, with_four)
