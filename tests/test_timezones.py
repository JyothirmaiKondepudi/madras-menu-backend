"""Event times are local to the venue: the project's timezone, else the org's
(America/New_York by default). Times without an offset are read there; the API
returns the exact instant plus the same time shown in the venue's timezone."""
from datetime import datetime, timezone


def _project(client, headers, vendor_id, start, end=None, **extra):
    resp = client.post("/projects", json={
        "projectName": "Timezone Test",
        "projectStatus": "Proposal",
        "projectStartDate": start,
        "projectEndDate": end or start,
        "vendorOnProject": vendor_id,
        **extra,
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _utc(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def test_naive_time_is_read_in_org_timezone(client, vendor_auth_headers, test_user):
    # December: New York is UTC-5
    project = _project(client, vendor_auth_headers, test_user["userId"], "2026-12-05T19:00:00")
    assert project["effectiveTimezone"] == "America/New_York"
    assert _utc(project["projectStartDate"]) == "2026-12-06T00:00:00"
    assert project["localStartDate"] == "2026-12-05T19:00:00-05:00"


def test_daylight_saving_is_applied(client, vendor_auth_headers, test_user):
    # July: New York is UTC-4
    project = _project(client, vendor_auth_headers, test_user["userId"], "2026-07-05T19:00:00")
    assert _utc(project["projectStartDate"]) == "2026-07-05T23:00:00"
    assert project["localStartDate"] == "2026-07-05T19:00:00-04:00"


def test_project_timezone_overrides_org(client, vendor_auth_headers, test_user):
    project = _project(
        client, vendor_auth_headers, test_user["userId"], "2026-12-05T19:00:00", projectTimezone="Asia/Kolkata"
    )
    assert project["effectiveTimezone"] == "Asia/Kolkata"
    assert _utc(project["projectStartDate"]) == "2026-12-05T13:30:00"
    assert project["localStartDate"] == "2026-12-05T19:00:00+05:30"


def test_time_with_offset_is_kept_as_given(client, vendor_auth_headers, test_user):
    project = _project(client, vendor_auth_headers, test_user["userId"], "2026-12-05T19:00:00+00:00")
    assert _utc(project["projectStartDate"]) == "2026-12-05T19:00:00"
    assert project["localStartDate"] == "2026-12-05T14:00:00-05:00"


def test_subproject_uses_project_timezone(client, vendor_auth_headers, test_user):
    project = _project(
        client, vendor_auth_headers, test_user["userId"], "2026-12-05T19:00:00", projectTimezone="America/Chicago"
    )
    resp = client.post("/subprojects", json={
        "subprojectName": "Reception",
        "projectAssociatedTo": project["projectId"],
        "cuisine": ["South Indian"],
        "religion": "Hindu",
        "subprojectDate": "2026-12-05T19:00:00",
        "guestCount": 100,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["effectiveTimezone"] == "America/Chicago"
    assert _utc(resp.json()["subprojectDate"]) == "2026-12-06T01:00:00"
    assert resp.json()["localSubprojectDate"] == "2026-12-05T19:00:00-06:00"


def test_changing_project_timezone_rereads_dates_in_same_request(client, vendor_auth_headers, test_user):
    project = _project(client, vendor_auth_headers, test_user["userId"], "2026-12-05T19:00:00")
    resp = client.patch(f"/projects/{project['projectId']}", json={
        "projectTimezone": "Asia/Kolkata",
        "projectStartDate": "2026-12-05T19:00:00",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["localStartDate"] == "2026-12-05T19:00:00+05:30"


def test_invalid_timezone_rejected(client, vendor_auth_headers, test_user):
    resp = client.post("/projects", json={
        "projectName": "Bad Zone",
        "projectStatus": "Proposal",
        "projectStartDate": "2026-12-05T19:00:00",
        "projectEndDate": "2026-12-05T23:00:00",
        "vendorOnProject": test_user["userId"],
        "projectTimezone": "Asia/Kolkatta",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 422


def test_payment_time_without_offset_rejected(client, vendor_auth_headers, test_user, test_project):
    invoice = client.post("/invoices", json={
        "invoiceStatus": "Generated",
        "totalAmount": 100,
        "depositPercentage": 100,
        "invoiceAssignedTo": test_user["userId"],
        "projectAssociatedTo": test_project["projectId"],
    }, headers=vendor_auth_headers).json()
    resp = client.post("/billing-history/payments", json={
        "invoiceId": invoice["invoiceId"], "amount": 50, "occurredAt": "2026-10-04T10:00:00",
    }, headers=vendor_auth_headers)
    assert resp.status_code == 422
