import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def _subproject_body(project_id):
    return {
        "subprojectName": "Wedding Reception Dinner",
        "projectAssociatedTo": project_id,
        "subprojectDate": "2026-11-14T19:00:00",
        "guestCount": 150,
        "subprojectType": "Buffet",
        "subprojectVenue": "Hotel",
        "subprojectEvent": "Wedding Dinner",
        "minPricePerPerson": 45.0,
        "maxPricePerPerson": 65.0,
    }


def test_create_subproject(client, test_project, vendor_auth_headers):
    resp = client.post(
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["subprojectName"] == "Wedding Reception Dinner"
    assert resp.json()["cuisine"] == []
    assert resp.json()["religion"] is None


def test_create_subproject_requires_vendor(client, test_project, test_client_login):
    login_resp = client.post(
        "/auth/login",
        json={
            "email": test_client_login["userEmail"],
            "password": "correct-horse-battery-staple",
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.post(
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_get_subproject_includes_nested_project_and_client(
    client, test_user, test_project, vendor_auth_headers
):
    created = client.post(
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.get(
        f"/subprojects/{created['subprojectId']}", headers=vendor_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["project"]["projectId"] == test_project["projectId"]
    assert [c["userId"] for c in body["project"]["clients"]] == [test_user["userId"]]


def test_get_subprojects_by_project_id(client, test_project, vendor_auth_headers):
    created = client.post(
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
        headers=vendor_auth_headers,
    ).json()

    resp = client.get(
        f"/projects/{test_project['projectId']}/subprojects",
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200
    assert any(s["subprojectId"] == created["subprojectId"] for s in resp.json()["items"])


def test_get_nonexistent_subproject_returns_404(client, vendor_auth_headers):
    resp = client.get(
        "/subprojects/00000000-0000-0000-0000-000000000000", headers=vendor_auth_headers
    )
    assert resp.status_code == 404


def test_get_subprojects_requires_auth(client):
    assert client.get("/subprojects").status_code == 401


def test_client_only_sees_subprojects_for_linked_projects(
    client, test_project, test_client_login, vendor_auth_headers
):
    client.post(
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
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

    resp = client.get("/subprojects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []

    client.post(
        f"/projects/{test_project['projectId']}/users/{test_client_login['userId']}",
        headers=vendor_auth_headers,
    )
    resp = client.get("/subprojects", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()["items"]) == 1


def test_corrected_choice_values_are_accepted(
    client, test_project, vendor_auth_headers
):
    body = _subproject_body(test_project["projectId"])
    body.update(subprojectVenue="Museum", subprojectEvent="Cocktail Hour")
    resp = client.post("/subprojects", json=body, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["subprojectVenue"] == "Museum"
    assert resp.json()["subprojectEvent"] == "Cocktail Hour"


def test_old_misspelled_choice_values_are_rejected(
    client, test_project, vendor_auth_headers
):
    for field, old_value in [
        ("subprojectVenue", "Mueseum"),
        ("subprojectEvent", "cockatail hour"),
    ]:
        body = _subproject_body(test_project["projectId"])
        body[field] = old_value
        resp = client.post("/subprojects", json=body, headers=vendor_auth_headers)
        assert resp.status_code == 422, (field, resp.text)


def test_database_rejects_values_outside_the_choices(
    engine, client, test_project, vendor_auth_headers
):
    # the CHECK constraint is the backstop for anything that skips the schemas
    created = client.post(
        "/subprojects",
        json=_subproject_body(test_project["projectId"]),
        headers=vendor_auth_headers,
    ).json()
    with pytest.raises(IntegrityError, match="subprojects_venue_check"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE subprojects SET venue = 'Mueseum' WHERE subproject_id = :id"
                ),
                {"id": created["subprojectId"]},
            )


def _subproject_with_cuisine(client, project_id, headers):
    body = _subproject_body(project_id) | {"cuisine": ["South Indian", "Chettinad"]}
    resp = client.post("/subprojects", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_update_rejects_null_cuisine(client, test_project, vendor_auth_headers):
    # a NULL cuisine would make every later read of this subproject a 500
    # (SubprojectOut.cuisine is a list), so null is rejected; [] means none
    created = _subproject_with_cuisine(client, test_project["projectId"], vendor_auth_headers)
    resp = client.patch(
        f"/subprojects/{created['subprojectId']}",
        json={"cuisine": None},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 422, resp.text

    # and the subproject still reads fine with its cuisines intact
    resp = client.get(f"/subprojects/{created['subprojectId']}", headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["cuisine"] == ["South Indian", "Chettinad"]


def test_update_can_clear_cuisine_with_empty_list(client, test_project, vendor_auth_headers):
    created = _subproject_with_cuisine(client, test_project["projectId"], vendor_auth_headers)
    resp = client.patch(
        f"/subprojects/{created['subprojectId']}",
        json={"cuisine": []},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cuisine"] == []


def test_update_without_cuisine_keeps_it(client, test_project, vendor_auth_headers):
    created = _subproject_with_cuisine(client, test_project["projectId"], vendor_auth_headers)
    resp = client.patch(
        f"/subprojects/{created['subprojectId']}",
        json={"guestCount": 200},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["guestCount"] == 200
    assert resp.json()["cuisine"] == ["South Indian", "Chettinad"]


def test_update_rejects_null_event_date(client, test_project, vendor_auth_headers):
    # used to reach the timezone conversion and crash with a 500
    created = _subproject_with_cuisine(client, test_project["projectId"], vendor_auth_headers)
    resp = client.patch(
        f"/subprojects/{created['subprojectId']}",
        json={"subprojectDate": None},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 422, resp.text

    resp = client.get(f"/subprojects/{created['subprojectId']}", headers=vendor_auth_headers)
    assert resp.json()["subprojectDate"] == created["subprojectDate"]


# --- catering brief (BE-05) ---------------------------------------------------


def test_create_subproject_with_catering_brief(client, test_project, vendor_auth_headers):
    body = _subproject_body(test_project["projectId"]) | {
        "venueName": "Hyatt Regency Ballroom",
        "venueAddress": "1 Main St, Tampa, FL",
        "diet": ["Vegetarian", "Jain"],
        "allergies": ["Peanuts", "Shellfish"],
        "theme": "Royal Rajasthani",
        "themeNotes": "Marigold garlands, brass serveware",
    }
    resp = client.post("/subprojects", json=body, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text

    saved = client.get(f"/subprojects/{resp.json()['subprojectId']}", headers=vendor_auth_headers).json()
    for field in ("venueName", "venueAddress", "diet", "allergies", "theme", "themeNotes"):
        assert saved[field] == body[field], field


def test_catering_brief_is_optional(client, test_project, vendor_auth_headers):
    # existing callers that send none of the new fields keep working
    resp = client.post("/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["diet"] == [] and body["allergies"] == []
    assert body["venueName"] is None and body["theme"] is None


def test_diet_must_come_from_the_picklist(client, test_project, vendor_auth_headers):
    body = _subproject_body(test_project["projectId"]) | {"diet": ["Vegetarian", "Paleo"]}
    resp = client.post("/subprojects", json=body, headers=vendor_auth_headers)
    assert resp.status_code == 422, resp.text


def test_update_catering_brief(client, test_project, vendor_auth_headers):
    created = _subproject_with_cuisine(client, test_project["projectId"], vendor_auth_headers)
    resp = client.patch(
        f"/subprojects/{created['subprojectId']}",
        json={"diet": ["Halal"], "allergies": ["Sesame"], "venueName": "Community Hall"},
        headers=vendor_auth_headers,
    )
    assert resp.status_code == 200, resp.text

    saved = client.get(f"/subprojects/{created['subprojectId']}", headers=vendor_auth_headers).json()
    assert saved["diet"] == ["Halal"]
    assert saved["allergies"] == ["Sesame"]
    assert saved["venueName"] == "Community Hall"


@pytest.mark.parametrize("field", ["diet", "allergies"])
def test_update_rejects_null_brief_lists(client, test_project, vendor_auth_headers, field):
    created = _subproject_with_cuisine(client, test_project["projectId"], vendor_auth_headers)
    resp = client.patch(
        f"/subprojects/{created['subprojectId']}", json={field: None}, headers=vendor_auth_headers
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("field", ["subprojectType", "subprojectVenue", "subprojectEvent"])
def test_other_is_accepted_for_each_choice_list(client, test_project, vendor_auth_headers, field):
    body = _subproject_body(test_project["projectId"]) | {field: "Other"}
    resp = client.post("/subprojects", json=body, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()[field] == "Other"


def test_database_rejects_a_diet_outside_the_picklist(engine, client, test_project, vendor_auth_headers):
    # the CHECK constraint is the backstop for anything that skips the schemas
    created = client.post(
        "/subprojects", json=_subproject_body(test_project["projectId"]), headers=vendor_auth_headers
    ).json()
    with pytest.raises(IntegrityError, match="subprojects_diet_check"):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE subprojects SET diet = ARRAY['Paleo'] WHERE subproject_id = :id"),
                {"id": created["subprojectId"]},
            )
