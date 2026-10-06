"""Regression tests for main.py's global exception handlers — each one
maps to a real bug this session found and fixed, not a hypothetical."""
import json

import pytest
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from main import handle_integrity_error


def _assert_no_database_details(resp):
    # the raw Postgres error names tables, constraints and values; none of it
    # should reach the client
    body = resp.text.lower()
    for leak in ("constraint", "violates", "key (", "menu_items", "item_relationships", "detail:"):
        assert leak not in body, f"{leak!r} leaked in {resp.text}"


def test_deleting_referenced_menu_item_returns_409_not_500(client, vendor_auth_headers):
    child = client.post("/menu-items", json={
        "name": "Basmati Peas Pilaf", "course": "main", "vegNonveg": "veg", "priceWeight": "standard",
    }, headers=vendor_auth_headers).json()
    parent = client.post("/menu-items", json={
        "name": "Basmati Pilaf", "course": "main", "vegNonveg": "veg", "priceWeight": "standard",
    }, headers=vendor_auth_headers).json()
    client.post(
        "/item-relationships", json={"childId": child["id"], "parentId": parent["id"]}, headers=vendor_auth_headers
    )

    # parent is still referenced by the edge above — deleting it must fail
    # cleanly (409), not leak a raw IntegrityError as a 500
    resp = client.delete(f"/menu-items/{parent['id']}", headers=vendor_auth_headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "This record is linked to other records."
    _assert_no_database_details(resp)

    # and it must genuinely still exist afterward — the failed delete
    # should not have partially applied
    assert client.get(f"/menu-items/{parent['id']}", headers=vendor_auth_headers).status_code == 200


def test_duplicate_menu_item_name_returns_409(client, vendor_auth_headers):
    body = {"name": "Unique Dish", "course": "main", "vegNonveg": "veg", "priceWeight": "standard"}
    first = client.post("/menu-items", json=body, headers=vendor_auth_headers)
    assert first.status_code == 200

    second = client.post("/menu-items", json=body, headers=vendor_auth_headers)
    assert second.status_code == 409
    assert second.json()["detail"] == "A record with these details already exists."
    _assert_no_database_details(second)


class _FakePgError(Exception):
    def __init__(self, pgcode):
        super().__init__('new row for relation "secret_table" violates constraint "secret_check"')
        self.pgcode = pgcode


@pytest.mark.parametrize("pgcode, status, detail", [
    ("23505", 409, "A record with these details already exists."),
    ("23503", 409, "This record is linked to other records."),
    ("23502", 422, "A required field is missing."),
    ("23514", 422, "One of the values isn't allowed."),
    ("23P01", 409, "The request conflicts with existing data."),
    (None, 409, "The request conflicts with existing data."),
])
def test_integrity_errors_map_to_safe_messages(pgcode, status, detail):
    request = Request({"type": "http", "method": "POST", "path": "/anything", "headers": []})
    exc = IntegrityError("INSERT ...", {}, _FakePgError(pgcode))

    resp = handle_integrity_error(request, exc)

    assert resp.status_code == status
    assert json.loads(resp.body) == {"detail": detail}
    assert b"secret" not in resp.body
