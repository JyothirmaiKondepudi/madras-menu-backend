import pytest


def _invoice_body(project_id, user_id, **overrides):
    body = {
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": user_id,
        "projectAssociatedTo": project_id,
    }
    body.update(overrides)
    return body


def test_create_invoice(client, test_user, test_project, vendor_auth_headers):
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"], test_user["userId"], totalAmount=2500.0
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAmount"] == 2500.00
    assert resp.json()["project"]["projectId"] == test_project["projectId"]


def test_create_invoice_requires_vendor(
    client, test_user, test_project, test_client_login
):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_invoice_by_id(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.get(f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["invoiceId"] == created["invoiceId"]


def test_get_nonexistent_invoice_returns_404(client, vendor_auth_headers):
    resp = client.get(
        "/invoices/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_get_invoices_requires_auth(client):
    assert client.get("/invoices").status_code == 401


def test_client_only_sees_own_invoices(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    )
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.get("/invoices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_client_cannot_view_another_users_invoice(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.get(
        f"/invoices/{created['invoiceId']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_invoices_by_project_id(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.get(
        f"/projects/{test_project['projectId']}/invoices", headers=vendor_auth_headers
    )
    assert resp.status_code == 200
    assert any(i["invoiceId"] == created["invoiceId"] for i in resp.json()["items"])


def test_get_invoices_by_project_id_forbidden_for_unlinked_client(
    client, test_project, test_client_login
):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.get(
        f"/projects/{test_project['projectId']}/invoices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_update_invoice(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"totalAmount": 200.0},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAmount"] == 200.00


# --- invoice status lifecycle (ticket C7) ------------------------------------


def test_new_invoice_starts_assigned_whatever_status_is_sent(
    client, test_user, test_project, vendor_auth_headers
):
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"], test_user["userId"], invoiceStatus="Paid"
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Assigned"


def test_patch_cannot_change_status(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"invoiceStatus": "Paid"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Assigned"


def test_declined_invoice_is_final(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    client.post(
        f"/invoices/{created['invoiceId']}/reject", headers=vendor_auth_headers
    )

    resp = client.post(
        f"/invoices/{created['invoiceId']}/accept", headers=vendor_auth_headers
    )
    assert resp.status_code == 409, resp.text
    assert "Declined invoices can't be changed to Accepted" in resp.json()["detail"]


def test_update_invoice_regenerates_pdf(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"], test_user["userId"], totalAmount=100.0
        ),
        headers=vendor_auth_headers,
    ).json()

    original_pdf = client.get(
        f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers
    ).content

    client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"totalAmount": 999.0},
        headers=vendor_auth_headers,
    )

    updated_pdf = client.get(
        f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers
    ).content
    # reportlab compresses content, so just check the file actually changed
    assert updated_pdf != original_pdf


def test_delete_invoice(client, test_user, test_project, vendor_auth_headers):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.delete(
        f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 204
    assert (
        client.get(
            f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers
        ).status_code
        == 404
    )


def test_deleted_invoice_is_hidden_but_kept(
    client, engine, test_user, test_project, vendor_auth_headers
):
    from sqlalchemy import text

    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    invoice_id = created["invoiceId"]
    assert (
        client.delete(
            f"/invoices/{invoice_id}", headers=vendor_auth_headers
        ).status_code
        == 204
    )

    # gone from every read, and deleting again is a 404
    listed = client.get("/invoices", headers=vendor_auth_headers).json()["items"]
    assert invoice_id not in [i["invoiceId"] for i in listed]
    by_project = client.get(
        f"/projects/{test_project['projectId']}/invoices", headers=vendor_auth_headers
    ).json()["items"]
    assert invoice_id not in [i["invoiceId"] for i in by_project]
    assert (
        client.delete(
            f"/invoices/{invoice_id}", headers=vendor_auth_headers
        ).status_code
        == 404
    )

    # but the row is still there, and still blocks deleting its project
    with engine.connect() as conn:
        deleted_at = conn.execute(
            text("SELECT invoice_deleted_at FROM invoices WHERE invoice_id = :id"),
            {"id": invoice_id},
        ).scalar()
    assert deleted_at is not None
    resp = client.delete(
        f"/projects/{test_project['projectId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 409, resp.text


def test_accepted_invoice_cannot_be_deleted(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    client.post(
        f"/invoices/{created['invoiceId']}/accept", headers=vendor_auth_headers
    )
    resp = client.delete(
        f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 409
    assert (
        client.get(
            f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers
        ).status_code
        == 200
    )


def test_invoice_with_payment_cannot_be_deleted(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    client.post(
        f"/invoices/{created['invoiceId']}/accept", headers=vendor_auth_headers
    )
    paid = client.post(
        "/billing-history/payments",
        json={"invoiceId": created["invoiceId"], "amount": 10},
        headers=vendor_auth_headers,
    )
    assert paid.status_code == 200, paid.text
    resp = client.delete(
        f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 409


def test_invoice_pdf_generated_and_downloadable(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"], test_user["userId"], totalAmount=250.0
        ),
        headers=vendor_auth_headers,
    ).json()

    resp = client.get(
        f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def _break_pdf_generation(monkeypatch):
    def failing_generate(invoice, assigned_user):
        raise OSError("disk full")

    # regenerate_pdf looks the generator up in services.invoices
    monkeypatch.setattr("services.invoices.generate_invoice_pdf", failing_generate)


def test_invoice_is_created_even_if_pdf_fails(
    client, test_user, test_project, vendor_auth_headers, monkeypatch
):
    # the PDF runs after the commit: a failure is logged, not a failed request,
    # or the caller would retry and create the invoice twice
    _break_pdf_generation(monkeypatch)
    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    invoice_id = resp.json()["invoiceId"]
    resp = client.get(f"/invoices/{invoice_id}", headers=vendor_auth_headers)
    assert resp.status_code == 200


def test_invoice_update_is_saved_even_if_pdf_fails(
    client, test_user, test_project, vendor_auth_headers, monkeypatch
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    _break_pdf_generation(monkeypatch)
    resp = client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"totalAmount": "999.00"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = client.get(f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers)
    assert resp.json()["totalAmount"] == 999.00


def test_invoice_accept_is_saved_even_if_pdf_fails(
    client, test_user, test_project, vendor_auth_headers, monkeypatch
):
    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    _break_pdf_generation(monkeypatch)
    resp = client.post(
        f"/invoices/{created['invoiceId']}/accept", headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text

    resp = client.get(f"/invoices/{created['invoiceId']}", headers=vendor_auth_headers)
    assert resp.json()["invoiceStatus"] == "Accepted"


def test_missing_pdf_is_regenerated_on_download(
    client, test_user, test_project, vendor_auth_headers
):
    from services.invoice_pdf import invoice_pdf_path

    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    # e.g. the PDF failed after the commit
    invoice_pdf_path(created["invoiceId"]).unlink()

    resp = client.get(
        f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF")


def test_download_returns_503_when_pdf_cannot_be_regenerated(
    client, test_user, test_project, vendor_auth_headers, monkeypatch
):
    from services.invoice_pdf import invoice_pdf_path

    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    invoice_pdf_path(created["invoiceId"]).unlink()

    # unlike create/update, nothing was saved here: the PDF is what was
    # asked for, so failing to produce it is the caller's error to see
    _break_pdf_generation(monkeypatch)
    resp = client.get(
        f"/invoices/{created['invoiceId']}/pdf", headers=vendor_auth_headers
    )
    assert resp.status_code == 503, resp.text


def test_invoice_pdf_requires_auth(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"], test_user["userId"], totalAmount=250.0
        ),
        headers=vendor_auth_headers,
    ).json()

    assert client.get(f"/invoices/{created['invoiceId']}/pdf").status_code == 401


def test_invoice_pdf_forbidden_for_another_user(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"], test_user["userId"], totalAmount=250.0
        ),
        headers=vendor_auth_headers,
    ).json()
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.get(
        f"/invoices/{created['invoiceId']}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def _project_with_vendor_and_client(client, vendor_id, client_id, headers):
    project = client.post(
        "/projects",
        json={
            "projectName": "Notification Test Project",
            "projectStatus": "Proposal",
            "projectStartDate": "2026-11-14T18:00:00",
            "projectEndDate": "2026-11-14T23:00:00",
            "vendorOnProject": vendor_id,
        },
        headers=headers,
    ).json()
    if client_id is not None:
        client.post(
            f"/projects/{project['projectId']}/users/{client_id}", headers=headers
        )
    return project


def _login(client, email, password="correct-horse-battery-staple"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_client_accepting_invoice_notifies_both_client_and_vendor(
    client, test_vendor_login, test_client_login, vendor_auth_headers
):
    project = _project_with_vendor_and_client(
        client,
        test_vendor_login["userId"],
        test_client_login["userId"],
        vendor_auth_headers,
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=vendor_auth_headers,
    ).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.post(
        f"/invoices/{invoice['invoiceId']}/accept",
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Accepted"

    # both the acting client and the project's vendor should get a notification
    client_unread = client.get(
        "/notifications/unread", headers={"Authorization": f"Bearer {client_token}"}
    ).json()["items"]
    assert any(n["type"] == "invoice_accepted" for n in client_unread)

    vendor_token = _login(client, test_vendor_login["userEmail"])
    vendor_unread = client.get(
        "/notifications/unread", headers={"Authorization": f"Bearer {vendor_token}"}
    ).json()["items"]
    assert any(n["type"] == "invoice_accepted" for n in vendor_unread)


def test_reject_invoice_sets_declined_status(
    client, test_vendor_login, test_client_login, vendor_auth_headers
):
    project = _project_with_vendor_and_client(
        client,
        test_vendor_login["userId"],
        test_client_login["userId"],
        vendor_auth_headers,
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=vendor_auth_headers,
    ).json()

    client_token = _login(client, test_client_login["userEmail"])
    resp = client.post(
        f"/invoices/{invoice['invoiceId']}/reject",
        headers={"Authorization": f"Bearer {client_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceStatus"] == "Declined"


def test_accept_invoice_requires_being_the_billed_client_or_vendor(
    client, test_user, test_project, test_client_login, vendor_auth_headers
):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    other_token = _login(client, test_client_login["userEmail"])
    resp = client.post(
        f"/invoices/{invoice['invoiceId']}/accept",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_accept_invoice_requires_auth(
    client, test_user, test_project, vendor_auth_headers
):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    assert client.post(f"/invoices/{invoice['invoiceId']}/accept").status_code == 401


def test_invoice_amount_is_deposit_percentage_of_total(
    client, test_user, test_project, vendor_auth_headers
):
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            totalAmount=10000.0,
            depositPercentage=25,
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["invoiceAmount"] == 2500.00
    assert body["totalAmount"] == 10000.00
    assert body["depositPercentage"] == 25.00


def test_invoice_amount_rounds_to_the_cent(
    client, test_user, test_project, vendor_auth_headers
):
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            totalAmount=1000.0,
            depositPercentage=33.33,
        ),
        headers=vendor_auth_headers,
    )
    assert resp.json()["invoiceAmount"] == 333.30


def test_deposit_percentage_out_of_range_rejected(
    client, test_user, test_project, vendor_auth_headers
):
    for pct in (0, -5, 150):
        resp = client.post(
            "/invoices",
            json=_invoice_body(
                test_project["projectId"], test_user["userId"], depositPercentage=pct
            ),
            headers=vendor_auth_headers,
        )
        assert resp.status_code == 422, pct


def test_updating_deposit_percentage_recomputes_amount(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            totalAmount=8000.0,
            depositPercentage=25,
        ),
        headers=vendor_auth_headers,
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"depositPercentage": 50},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAmount"] == 4000.00


def test_invoice_audit_timestamps(client, test_user, test_project, vendor_auth_headers):
    from datetime import datetime

    created = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    created_at = datetime.fromisoformat(created["createdAt"])
    assert created_at.tzinfo is not None

    resp = client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"totalAmount": 150.0},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert datetime.fromisoformat(resp.json()["createdAt"]) == created_at
    assert datetime.fromisoformat(resp.json()["updatedAt"]) > datetime.fromisoformat(
        created["updatedAt"]
    )


# --- due dates (ticket C6) ---------------------------------------------------


def _utc(value):
    from datetime import datetime, timezone

    return (
        datetime.fromisoformat(value)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
        .isoformat()
    )


def _create_subproject(
    client, project_id, headers, subproject_date="2026-12-01T19:00:00"
):
    resp = client.post(
        "/subprojects",
        json={
            "subprojectName": "Due Date Test Subproject",
            "projectAssociatedTo": project_id,
            "cuisine": ["South Indian"],
            "religion": "Hindu",
            "subprojectDate": subproject_date,
            "guestCount": 50,
            "subprojectType": "Buffet",
            "subprojectVenue": "Hotel",
            "subprojectEvent": "Wedding Dinner",
            "minPricePerPerson": 40.0,
            "maxPricePerPerson": 60.0,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_due_date_defaults_to_seven_days_before_event(
    client, test_user, test_project, vendor_auth_headers
):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=subproject["subprojectId"],
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    # event is Dec 1 19:00 New York (00:00 UTC Dec 2), so due Nov 24 19:00 New York
    assert _utc(resp.json()["dueDate"]) == "2026-11-25T00:00:00"


def test_vendor_due_date_overrides_default(
    client, test_user, test_project, vendor_auth_headers
):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=subproject["subprojectId"],
            dueDate="2026-11-15T09:00:00",
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    # a date without an offset is read in the venue's timezone (New York, EST)
    assert _utc(resp.json()["dueDate"]) == "2026-11-15T14:00:00"


def test_vendor_due_date_with_offset_is_kept_as_given(
    client, test_user, test_project, vendor_auth_headers
):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=subproject["subprojectId"],
            dueDate="2026-11-15T09:00:00+05:30",
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert _utc(resp.json()["dueDate"]) == "2026-11-15T03:30:00"


def test_project_level_invoice_has_no_default_due_date(
    client, test_user, test_project, vendor_auth_headers
):
    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["dueDate"] is None


def test_project_level_invoice_keeps_vendor_due_date(
    client, test_user, test_project, vendor_auth_headers
):
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            dueDate="2026-10-25T09:00:00",
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    # read in the project's timezone (New York, still EDT on Oct 25)
    assert _utc(resp.json()["dueDate"]) == "2026-10-25T13:00:00"


def test_updated_due_date_is_read_in_venue_timezone(
    client, test_user, test_project, vendor_auth_headers
):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    created = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=subproject["subprojectId"],
        ),
        headers=vendor_auth_headers,
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"dueDate": "2026-11-15T09:00:00"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    # New York in November is UTC-5
    assert _utc(resp.json()["dueDate"]) == "2026-11-15T14:00:00"


def test_due_date_can_be_cleared(client, test_user, test_project, vendor_auth_headers):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    created = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=subproject["subprojectId"],
        ),
        headers=vendor_auth_headers,
    ).json()

    resp = client.patch(
        f"/invoices/{created['invoiceId']}",
        json={"dueDate": None},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["dueDate"] is None


# --- rescheduling the event moves due dates with it (ticket C6) -------------


def _invoice_on(client, test_project, test_user, headers, subproject_id, **overrides):
    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=subproject_id,
            **overrides,
        ),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _reschedule(client, subproject_id, new_date, headers):
    resp = client.patch(
        f"/subprojects/{subproject_id}",
        json={"subprojectDate": new_date},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def _due_date(client, invoice_id, headers):
    return _utc(
        client.get(f"/invoices/{invoice_id}", headers=headers).json()["dueDate"]
    )


def test_rescheduling_event_shifts_due_dates(
    client, test_user, test_project, vendor_auth_headers
):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    default = _invoice_on(
        client, test_project, test_user, vendor_auth_headers, subproject["subprojectId"]
    )
    custom = _invoice_on(
        client,
        test_project,
        test_user,
        vendor_auth_headers,
        subproject["subprojectId"],
        dueDate="2026-11-17T19:00:00",  # 14 days before the event
    )

    # Dec 1 -> Dec 11, same time of day
    _reschedule(
        client, subproject["subprojectId"], "2026-12-11T19:00:00", vendor_auth_headers
    )

    assert (
        _due_date(client, default["invoiceId"], vendor_auth_headers)
        == "2026-12-05T00:00:00"
    )
    # still 14 days before the event
    assert (
        _due_date(client, custom["invoiceId"], vendor_auth_headers)
        == "2026-11-28T00:00:00"
    )


def test_rescheduling_keeps_due_dates_of_accepted_and_paid_invoices(
    client, test_user, test_project, vendor_auth_headers
):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    accepted = _invoice_on(
        client, test_project, test_user, vendor_auth_headers, subproject["subprojectId"]
    )
    client.post(
        f"/invoices/{accepted['invoiceId']}/accept", headers=vendor_auth_headers
    )
    paid = _invoice_on(
        client, test_project, test_user, vendor_auth_headers, subproject["subprojectId"]
    )
    client.post(f"/invoices/{paid['invoiceId']}/accept", headers=vendor_auth_headers)
    client.post(
        "/billing-history/payments",
        json={"invoiceId": paid["invoiceId"], "amount": 40},
        headers=vendor_auth_headers,
    )

    _reschedule(
        client, subproject["subprojectId"], "2026-12-11T19:00:00", vendor_auth_headers
    )

    assert (
        _due_date(client, accepted["invoiceId"], vendor_auth_headers)
        == "2026-11-25T00:00:00"
    )
    assert (
        _due_date(client, paid["invoiceId"], vendor_auth_headers)
        == "2026-11-25T00:00:00"
    )


def test_rescheduling_leaves_other_subprojects_alone(
    client, test_user, test_project, vendor_auth_headers
):
    moved = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    other = _create_subproject(client, test_project["projectId"], vendor_auth_headers)
    invoice = _invoice_on(
        client, test_project, test_user, vendor_auth_headers, other["subprojectId"]
    )

    _reschedule(
        client, moved["subprojectId"], "2026-12-11T19:00:00", vendor_auth_headers
    )

    assert (
        _due_date(client, invoice["invoiceId"], vendor_auth_headers)
        == "2026-11-25T00:00:00"
    )


def test_updating_subproject_without_new_date_keeps_due_dates(
    client, test_user, test_project, vendor_auth_headers
):
    subproject = _create_subproject(
        client, test_project["projectId"], vendor_auth_headers
    )
    invoice = _invoice_on(
        client, test_project, test_user, vendor_auth_headers, subproject["subprojectId"]
    )

    resp = client.patch(
        f"/subprojects/{subproject['subprojectId']}",
        json={"guestCount": 80},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    assert (
        _due_date(client, invoice["invoiceId"], vendor_auth_headers)
        == "2026-11-25T00:00:00"
    )


# --- invoice relationships (ticket C7) ---------------------------------------


def _org_client(client, headers, email):
    """A client in the vendor's org who isn't linked to any project."""
    resp = client.post(
        "/users",
        json={
            "fullName": "Unlinked Client",
            "email": email,
            "phoneNumber": "5550007777",
            "preferredContact": "email",
            "role": "client",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _other_project(client, vendor_id, headers):
    resp = client.post(
        "/projects",
        json={
            "projectName": "Other Project",
            "projectStatus": "Proposal",
            "projectStartDate": "2026-11-14T18:00:00",
            "projectEndDate": "2026-11-14T23:00:00",
            "vendorOnProject": vendor_id,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_invoice_cannot_be_assigned_to_a_non_member(
    client, test_project, vendor_auth_headers
):
    outsider = _org_client(client, vendor_auth_headers, "outsider@example.com")

    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], outsider["userId"]),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 422, resp.text
    assert "member of its project" in resp.json()["detail"]


def test_invoice_can_be_assigned_once_the_client_is_linked(
    client, test_project, vendor_auth_headers
):
    member = _org_client(client, vendor_auth_headers, "member@example.com")
    client.post(
        f"/projects/{test_project['projectId']}/users/{member['userId']}",
        headers=vendor_auth_headers,
    )

    resp = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], member["userId"]),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text


def test_invoice_cannot_be_reassigned_to_a_non_member(
    client, test_user, test_project, vendor_auth_headers
):
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()
    outsider = _org_client(client, vendor_auth_headers, "outsider@example.com")

    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}",
        json={"invoiceAssignedTo": outsider["userId"]},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 422, resp.text

    client.post(
        f"/projects/{test_project['projectId']}/users/{outsider['userId']}",
        headers=vendor_auth_headers,
    )
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}",
        json={"invoiceAssignedTo": outsider["userId"]},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAssignedTo"] == outsider["userId"]


def test_invoice_cannot_use_another_projects_subproject(test_vendor_login, 
    client, test_user, test_project, vendor_auth_headers
):
    other = _other_project(client, test_vendor_login["userId"], vendor_auth_headers)
    other_subproject = _create_subproject(
        client, other["projectId"], vendor_auth_headers
    )

    resp = client.post(
        "/invoices",
        json=_invoice_body(
            test_project["projectId"],
            test_user["userId"],
            subprojectId=other_subproject["subprojectId"],
        ),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 404, resp.text


def _insert_invoice(engine, **columns):
    """Writes an invoice straight to the database, skipping the API checks."""
    from decimal import Decimal
    from uuid import UUID

    from sqlalchemy.orm import Session

    from models import Invoice

    with Session(engine) as db:
        db.add(
            Invoice(
                invoiceStatus="Assigned",
                invoiceAmount=Decimal("100.00"),
                **{
                    key: UUID(value) if isinstance(value, str) else value
                    for key, value in columns.items()
                },
            )
        )
        db.commit()


def test_database_rejects_invoice_for_a_non_member(
    client, engine, test_project, vendor_auth_headers
):
    from sqlalchemy.exc import IntegrityError

    outsider = _org_client(client, vendor_auth_headers, "outsider@example.com")

    with pytest.raises(IntegrityError, match="invoices_assignee_project_member_fkey"):
        _insert_invoice(
            engine,
            invoiceAssignedTo=outsider["userId"],
            projectAssociatedTo=test_project["projectId"],
        )


def test_database_rejects_invoice_with_another_projects_subproject(test_vendor_login, 
    client, engine, test_user, test_project, vendor_auth_headers
):
    from sqlalchemy.exc import IntegrityError

    other = _other_project(client, test_vendor_login["userId"], vendor_auth_headers)
    other_subproject = _create_subproject(
        client, other["projectId"], vendor_auth_headers
    )

    with pytest.raises(IntegrityError, match="invoices_subproject_in_project_fkey"):
        _insert_invoice(
            engine,
            invoiceAssignedTo=test_user["userId"],
            projectAssociatedTo=test_project["projectId"],
            subprojectId=other_subproject["subprojectId"],
        )


def test_database_accepts_project_level_invoice_for_a_member(
    engine, test_user, test_project
):
    """Null subproject_id skips the subproject check; the member check still passes."""
    _insert_invoice(
        engine,
        invoiceAssignedTo=test_user["userId"],
        projectAssociatedTo=test_project["projectId"],
    )


# --- accept and reject are idempotent (ticket C7) ----------------------------


def _notifications_for(engine, invoice_id, kind):
    from uuid import UUID

    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from models import Notification

    with Session(engine) as db:
        return db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.relatedInvoiceId == UUID(invoice_id),
                Notification.type == kind,
            )
        )


@pytest.mark.parametrize(
    "action, status, kind",
    [
        ("accept", "Accepted", "invoice_accepted"),
        ("reject", "Declined", "invoice_declined"),
    ],
)
def test_repeating_an_answer_succeeds_without_notifying_again(
    client,
    engine,
    test_vendor_login,
    test_client_login,
    vendor_auth_headers,
    action,
    status,
    kind,
):
    project = _project_with_vendor_and_client(
        client,
        test_vendor_login["userId"],
        test_client_login["userId"],
        vendor_auth_headers,
    )
    invoice = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=vendor_auth_headers,
    ).json()
    client_headers = {
        "Authorization": f"Bearer {_login(client, test_client_login['userEmail'])}"
    }

    for _ in range(2):  # e.g. a double-click, or a retried request
        resp = client.post(
            f"/invoices/{invoice['invoiceId']}/{action}", headers=client_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["invoiceStatus"] == status

    # one for the client, one for the vendor; nothing from the repeat
    assert _notifications_for(engine, invoice["invoiceId"], kind) == 2


def test_client_and_vendor_accepting_together_notifies_once(
    client, engine, test_vendor_login, test_client_login, vendor_auth_headers
):
    """Both accept at the same moment: the second waits for the first's lock
    on the invoice, then sees it's already Accepted and does nothing."""
    import threading
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from models import Invoice
    from services.invoices import respond_to_invoice

    project = _project_with_vendor_and_client(
        client,
        test_vendor_login["userId"],
        test_client_login["userId"],
        vendor_auth_headers,
    )
    invoice_id = client.post(
        "/invoices",
        json=_invoice_body(project["projectId"], test_client_login["userId"]),
        headers=vendor_auth_headers,
    ).json()["invoiceId"]

    errors = []

    def second_accept():
        with Session(engine) as db:
            try:
                respond_to_invoice(db.get(Invoice, UUID(invoice_id)), "Accepted", db)
                db.commit()
            except Exception as exc:  # surfaced in the main thread below
                errors.append(exc)

    # closed in the with block even if an assertion fails, or the table
    # cleanup after the test would wait on its lock forever
    with Session(engine) as first:
        invoice = first.get(Invoice, UUID(invoice_id))
        # respond_to_invoice flushes, so hold the lock by hand while the
        # second accept starts and has to wait for it
        first.execute(
            select(Invoice)
            .where(Invoice.invoiceId == invoice.invoiceId)
            .with_for_update()
        )
        thread = threading.Thread(target=second_accept)
        thread.start()
        thread.join(timeout=1)
        waited = thread.is_alive()
        respond_to_invoice(invoice, "Accepted", first)
        first.commit()  # commits, releasing the lock

    thread.join(timeout=10)
    assert waited, "second accept didn't wait for the invoice lock"
    assert (
        not errors
    ), errors  # the repeat succeeds rather than failing as an invalid move
    assert _notifications_for(engine, invoice_id, "invoice_accepted") == 2


def test_client_cannot_be_removed_from_an_invoice(
    client, test_user, test_project, vendor_auth_headers
):
    """An explicit null used to reach the NOT NULL column and return a 500."""
    invoice = client.post(
        "/invoices",
        json=_invoice_body(test_project["projectId"], test_user["userId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}",
        json={"invoiceAssignedTo": None},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 422, resp.text
    assert "must stay assigned to a client" in resp.text

    # leaving the field out still works, and keeps the client
    resp = client.patch(
        f"/invoices/{invoice['invoiceId']}",
        json={"totalAmount": 150.0},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoiceAssignedTo"] == test_user["userId"]
