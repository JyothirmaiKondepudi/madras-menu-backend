"""BE-14: a project's timeline (activity + payments, merged and paged) and
follow-up tracking."""
import uuid


def _invoice(client, project_id, user_id, headers):
    resp = client.post("/invoices", json={
        "totalAmount": 500.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _timeline(client, project_id, headers, query=""):
    resp = client.get(f"/projects/{project_id}/activity{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _login(client, email):
    token = client.post("/auth/login", json={
        "email": email, "password": "correct-horse-battery-staple",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- the timeline ---------------------------------------------------------------


def test_timeline_merges_activity_and_payments_newest_first(
    client, test_user, test_project, vendor_auth_headers
):
    pid = test_project["projectId"]
    invoice = _invoice(client, pid, test_user["userId"], vendor_auth_headers)
    client.post(f"/invoices/{invoice['invoiceId']}/accept", headers=vendor_auth_headers)
    client.post("/billing-history/payments", json={"invoiceId": invoice["invoiceId"], "amount": 200},
                headers=vendor_auth_headers)

    entries = _timeline(client, pid, vendor_auth_headers)["items"]
    types = [e["type"] for e in entries]
    # the payment is the latest thing that happened, project creation the first
    assert types[0] == "Payment_Succeeded"
    assert types[-1] == "project_created"
    assert {"invoice_generated", "invoice_accepted"} <= set(types)

    [payment] = [e for e in entries if e["kind"] == "payment"]
    assert payment["amount"] == 200.0
    assert payment["description"] == "Payment received: $200.00"

    times = [e["occurredAt"] for e in entries]
    assert times == sorted(times, reverse=True)


def test_voided_payment_is_marked_and_the_void_is_on_the_timeline(
    client, test_user, test_project, vendor_auth_headers
):
    pid = test_project["projectId"]
    invoice = _invoice(client, pid, test_user["userId"], vendor_auth_headers)
    client.post(f"/invoices/{invoice['invoiceId']}/accept", headers=vendor_auth_headers)
    payment = client.post("/billing-history/payments", json={"invoiceId": invoice["invoiceId"], "amount": 50},
                          headers=vendor_auth_headers).json()
    client.post(f"/billing-history/{payment['id']}/void", json={"reason": "typo"}, headers=vendor_auth_headers)

    entries = _timeline(client, pid, vendor_auth_headers)["items"]
    [shown] = [e for e in entries if e["kind"] == "payment"]
    assert shown["voidedAt"] is not None
    assert shown["description"].endswith("(voided)")
    assert "payment_voided" in [e["type"] for e in entries]


def test_payments_on_a_deleted_invoice_leave_the_timeline(
    client, test_user, test_project, vendor_auth_headers, engine
):
    # deleting needs no live payments, so add the payment row directly, as a
    # card payment arriving later would
    from sqlalchemy import text

    pid = test_project["projectId"]
    invoice = _invoice(client, pid, test_user["userId"], vendor_auth_headers)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO billing_history (id, invoice_id, event_type, amount, occurred_at, source) "
            "VALUES (gen_random_uuid(), :inv, 'Payment_Declined', 10, now(), 'Stripe')"
        ), {"inv": invoice["invoiceId"]})
    assert any(e["kind"] == "payment" for e in _timeline(client, pid, vendor_auth_headers)["items"])

    client.delete(f"/invoices/{invoice['invoiceId']}", headers=vendor_auth_headers)
    assert not any(e["kind"] == "payment" for e in _timeline(client, pid, vendor_auth_headers)["items"])


def test_timeline_pages_across_both_kinds(client, test_user, test_project, vendor_auth_headers):
    pid = test_project["projectId"]
    invoice = _invoice(client, pid, test_user["userId"], vendor_auth_headers)
    client.post(f"/invoices/{invoice['invoiceId']}/accept", headers=vendor_auth_headers)
    for amount in (10, 20, 30):
        client.post("/billing-history/payments", json={"invoiceId": invoice["invoiceId"], "amount": amount},
                    headers=vendor_auth_headers)

    total = _timeline(client, pid, vendor_auth_headers)["total"]
    seen = []
    for offset in range(0, total, 2):
        page = _timeline(client, pid, vendor_auth_headers, f"?limit=2&offset={offset}")
        assert page["total"] == total
        seen += [e["id"] for e in page["items"]]
    assert len(seen) == len(set(seen)) == total


def test_timeline_is_vendor_only(client, test_project, test_client_login, vendor_auth_headers):
    client.post(f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
                headers=vendor_auth_headers)
    resp = client.get(f"/projects/{test_project['projectId']}/activity",
                      headers=_login(client, test_client_login["userEmail"]))
    assert resp.status_code == 403


def test_timeline_of_unknown_project_is_404(client, vendor_auth_headers):
    assert client.get(f"/projects/{uuid.uuid4()}/activity", headers=vendor_auth_headers).status_code == 404


# --- follow-ups -------------------------------------------------------------------


def test_recording_a_follow_up(client, test_project, test_vendor_login, vendor_auth_headers):
    pid = test_project["projectId"]
    resp = client.post(f"/projects/{pid}/follow-ups", json={
        "note": "Called about the menu tasting",
        "nextFollowUpAt": "2026-11-20T10:00:00Z",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["lastFollowedUpAt"] is not None
    assert resp.json()["nextFollowUpAt"].startswith("2026-11-20T10:00:00")

    # saved, not just returned
    project = client.get(f"/projects/{pid}", headers=vendor_auth_headers).json()
    assert project["nextFollowUpAt"].startswith("2026-11-20T10:00:00")

    [entry] = [e for e in _timeline(client, pid, vendor_auth_headers)["items"] if e["type"] == "followed_up"]
    assert "Called about the menu tasting" in entry["description"]
    assert entry["actorId"] == test_vendor_login["userId"]


def test_follow_up_without_a_next_date_clears_it(client, test_project, vendor_auth_headers):
    pid = test_project["projectId"]
    client.post(f"/projects/{pid}/follow-ups", json={"note": "first", "nextFollowUpAt": "2026-11-20T10:00:00Z"},
                headers=vendor_auth_headers)
    resp = client.post(f"/projects/{pid}/follow-ups", json={"note": "done, nothing planned"},
                       headers=vendor_auth_headers)
    assert resp.json()["nextFollowUpAt"] is None


def test_next_follow_up_without_offset_is_read_in_the_venue_timezone(test_vendor_login, client, test_user, vendor_auth_headers):
    project = client.post("/projects", json={
        "projectName": "NY Event",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-11-14T18:00:00",
        "projectEndDate": "2026-11-14T23:00:00",
        "vendorOnProject": test_vendor_login["userId"],
        "projectTimezone": "America/New_York",
    }, headers=vendor_auth_headers).json()
    resp = client.post(f"/projects/{project['projectId']}/follow-ups",
                       json={"note": "call", "nextFollowUpAt": "2026-11-20T10:00:00"},
                       headers=vendor_auth_headers)
    # 10:00 in New York (EST, UTC-5) is 15:00 UTC
    assert resp.json()["nextFollowUpAt"].startswith("2026-11-20T15:00:00")


def test_reschedule_next_follow_up_with_patch(client, test_project, vendor_auth_headers):
    pid = test_project["projectId"]
    resp = client.patch(f"/projects/{pid}", json={"nextFollowUpAt": "2026-12-01T09:00:00Z"},
                        headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["nextFollowUpAt"].startswith("2026-12-01T09:00:00")
    # rescheduling isn't a follow-up: nothing logged, last date untouched
    assert resp.json()["lastFollowedUpAt"] is None
    assert "followed_up" not in [e["type"] for e in _timeline(client, pid, vendor_auth_headers)["items"]]


def test_follow_up_needs_a_note(client, test_project, vendor_auth_headers):
    resp = client.post(f"/projects/{test_project['projectId']}/follow-ups", json={"note": ""},
                       headers=vendor_auth_headers)
    assert resp.status_code == 422


def test_clients_cant_record_follow_ups(client, test_project, test_client_login, vendor_auth_headers):
    client.post(f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
                headers=vendor_auth_headers)
    resp = client.post(f"/projects/{test_project['projectId']}/follow-ups", json={"note": "hi"},
                       headers=_login(client, test_client_login["userEmail"]))
    assert resp.status_code == 403
