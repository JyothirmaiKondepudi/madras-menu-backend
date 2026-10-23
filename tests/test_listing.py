"""BE-08: every list endpoint pages, sorts and filters the same way
(services/listing.py)."""
import pytest


def _tax(client, headers, name, rate="5.000", jurisdiction="FL"):
    resp = client.post(
        "/tax-categories",
        json={"name": name, "jurisdiction": jurisdiction, "ratePercent": rate},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _invoice(client, project_id, user_id, headers, **extra):
    resp = client.post("/invoices", json={
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
        **extra,
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _subproject(client, project_id, headers, **extra):
    resp = client.post("/subprojects", json={
        "subprojectName": "Event",
        "projectAssociatedTo": project_id,
        "subprojectDate": "2026-11-14T19:00:00",
        "guestCount": 50,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
        **extra,
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- the page shape and its limits ------------------------------------------


def test_list_returns_a_page(client, vendor_auth_headers):
    _tax(client, vendor_auth_headers, "food")
    body = client.get("/tax-categories", headers=vendor_auth_headers).json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert (body["total"], body["limit"], body["offset"]) == (1, 50, 0)
    assert [t["name"] for t in body["items"]] == ["food"]


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "limit=abc"])
def test_invalid_paging_is_rejected(client, vendor_auth_headers, query):
    assert client.get(f"/tax-categories?{query}", headers=vendor_auth_headers).status_code == 422


def test_pages_cover_every_row_exactly_once(client, vendor_auth_headers):
    names = {f"cat-{i}" for i in range(5)}
    for name in names:
        _tax(client, vendor_auth_headers, name)

    seen = []
    for offset in (0, 2, 4):
        page = client.get(
            f"/tax-categories?limit=2&offset={offset}", headers=vendor_auth_headers
        ).json()
        assert page["total"] == 5
        seen += [t["name"] for t in page["items"]]
    assert sorted(seen) == sorted(names)  # no repeats, nothing missing


# --- sorting -----------------------------------------------------------------


def test_sort_ascending_and_descending(client, vendor_auth_headers):
    for name in ("banana", "apple", "cherry"):
        _tax(client, vendor_auth_headers, name)
    up = client.get("/tax-categories?sort=name", headers=vendor_auth_headers).json()["items"]
    down = client.get("/tax-categories?sort=-name", headers=vendor_auth_headers).json()["items"]
    assert [t["name"] for t in up] == ["apple", "banana", "cherry"]
    assert [t["name"] for t in down] == ["cherry", "banana", "apple"]


def test_sorting_by_an_unknown_field_is_rejected(client, vendor_auth_headers):
    resp = client.get("/tax-categories?sort=secretColumn", headers=vendor_auth_headers)
    assert resp.status_code == 422
    assert "Choose from" in resp.json()["detail"]


# --- filters -------------------------------------------------------------------


def test_project_filters(test_vendor_login, client, test_user, vendor_auth_headers):
    def project(name, status, start):
        return client.post("/projects", json={
            "projectName": name,
            "projectStatus": status,
            "projectStartDate": start,
            "projectEndDate": start,
            "vendorOnProject": test_vendor_login["userId"],
        }, headers=vendor_auth_headers).json()["projectId"]

    gala = project("Spring Gala", "Accepted", "2027-03-01T18:00:00")
    project("Autumn Wedding", "Proposal", "2027-10-01T18:00:00")

    def ids(query):
        return {p["projectId"] for p in client.get(f"/projects?{query}", headers=vendor_auth_headers).json()["items"]}

    assert ids("status=Accepted") == {gala}
    assert ids("search=gala") == {gala}  # case-insensitive, part of the name
    assert ids("startFrom=2027-01-01T00:00:00Z&startTo=2027-06-30T00:00:00Z") == {gala}
    assert client.get("/projects?status=Bogus", headers=vendor_auth_headers).status_code == 422


def test_invoice_filters_including_overdue(client, test_user, test_project, vendor_auth_headers):
    pid, uid = test_project["projectId"], test_user["userId"]
    late = _invoice(client, pid, uid, vendor_auth_headers, dueDate="2020-01-01T00:00:00Z")
    client.post(f"/invoices/{late['invoiceId']}/accept", headers=vendor_auth_headers)
    # not overdue: due in the past, but never accepted, so nothing is owed yet
    unaccepted = _invoice(client, pid, uid, vendor_auth_headers, dueDate="2020-01-01T00:00:00Z")
    # not overdue: accepted, but not due yet
    future = _invoice(client, pid, uid, vendor_auth_headers, dueDate="2099-01-01T00:00:00Z")
    client.post(f"/invoices/{future['invoiceId']}/accept", headers=vendor_auth_headers)

    def ids(query):
        return {i["invoiceId"] for i in client.get(f"/invoices?{query}", headers=vendor_auth_headers).json()["items"]}

    assert ids("overdue=true") == {late["invoiceId"]}
    assert ids("status=Assigned") == {unaccepted["invoiceId"]}
    assert ids("dueFrom=2050-01-01T00:00:00Z") == {future["invoiceId"]}
    # the same filters work on the per-project list
    resp = client.get(f"/projects/{pid}/invoices?overdue=true", headers=vendor_auth_headers)
    assert {i["invoiceId"] for i in resp.json()["items"]} == {late["invoiceId"]}


def test_deleted_invoices_are_not_counted(client, test_user, test_project, vendor_auth_headers):
    kept = _invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    gone = _invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    client.delete(f"/invoices/{gone['invoiceId']}", headers=vendor_auth_headers)

    page = client.get("/invoices", headers=vendor_auth_headers).json()
    assert page["total"] == 1
    assert [i["invoiceId"] for i in page["items"]] == [kept["invoiceId"]]


def test_subproject_filters(client, test_project, vendor_auth_headers):
    pid = test_project["projectId"]
    mehendi = _subproject(client, pid, vendor_auth_headers, subprojectEvent="Mehendi",
                          subprojectDate="2026-12-01T18:00:00")
    _subproject(client, pid, vendor_auth_headers, subprojectEvent="Wedding Dinner",
                subprojectDate="2026-12-05T18:00:00")

    def ids(query):
        return {s["subprojectId"] for s in client.get(f"/subprojects?{query}", headers=vendor_auth_headers).json()["items"]}

    assert ids("eventType=Mehendi") == {mehendi["subprojectId"]}
    assert ids("dateTo=2026-12-02T00:00:00Z") == {mehendi["subprojectId"]}
    # default order is by event date, soonest first
    listed = client.get("/subprojects", headers=vendor_auth_headers).json()["items"]
    assert listed[0]["subprojectId"] == mehendi["subprojectId"]


def test_user_filters(client, test_user, test_vendor_login, vendor_auth_headers):
    def emails(query):
        return {u["userEmail"] for u in client.get(f"/users?{query}", headers=vendor_auth_headers).json()["items"]}

    assert test_user["userEmail"] in emails("role=client")
    assert test_user["userEmail"] not in emails("role=vendor")
    assert emails(f"search={test_user['userEmail'].split('@')[0].upper()}") == {test_user["userEmail"]}
    assert test_user["userEmail"] in emails("disabled=false")


def test_menu_item_filters(client, vendor_auth_headers):
    def item(name, course, veg, active=True):
        client.post("/menu-items", json={
            "name": name, "course": course, "vegNonveg": veg, "priceWeight": "standard", "active": active,
        }, headers=vendor_auth_headers)

    item("Paneer Tikka", "appetizer", "veg")
    item("Chicken 65", "appetizer", "nonveg")
    item("Old Dal", "main", "veg", active=False)

    def names(query):
        return {m["name"] for m in client.get(f"/menu-items?{query}", headers=vendor_auth_headers).json()["items"]}

    assert names("course=appetizer") == {"Paneer Tikka", "Chicken 65"}
    assert names("vegNonveg=veg&active=true") == {"Paneer Tikka"}
    assert names("search=tikka") == {"Paneer Tikka"}


def test_billing_history_filter(client, test_user, test_project, vendor_auth_headers):
    invoice = _invoice(client, test_project["projectId"], test_user["userId"], vendor_auth_headers)
    client.post(f"/invoices/{invoice['invoiceId']}/accept", headers=vendor_auth_headers)
    client.post("/billing-history/payments", json={"invoiceId": invoice["invoiceId"], "amount": 40},
                headers=vendor_auth_headers)

    succeeded = client.get("/billing-history?eventType=Payment_Succeeded", headers=vendor_auth_headers).json()
    refunds = client.get("/billing-history?eventType=Refund_Issued", headers=vendor_auth_headers).json()
    assert succeeded["total"] == 1 and refunds["total"] == 0


# --- scoping still applies -------------------------------------------------------


def test_total_counts_only_what_the_caller_may_see(
    client, test_project, test_client_login, vendor_auth_headers
):
    login = client.post("/auth/login", json={
        "email": test_client_login["userEmail"], "password": "correct-horse-battery-staple",
    }).json()["access_token"]
    client_auth = {"Authorization": f"Bearer {login}"}

    # the vendor sees test_project; the client isn't on it yet
    assert client.get("/projects", headers=vendor_auth_headers).json()["total"] >= 1
    assert client.get("/projects", headers=client_auth).json()["total"] == 0
