"""BE-07: an organization's business profile, rate card and equipment list."""
import pytest
from sqlalchemy.orm import sessionmaker

from auth.security import hash_password
from models import Organization, User

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture()
def other_vendor(client, engine):
    """A vendor in a second organization, with their own auth headers."""
    db = sessionmaker(bind=engine)()
    org = Organization(orgName="Other Caterers", orgEmail="other@example.com", orgDisabled=False)
    db.add(org)
    db.flush()
    db.add(User(fullName="Other Vendor", userEmail="other.vendor@example.com", userRole="vendor",
                userOrg=org.orgId, passwordHash=hash_password(PASSWORD)))
    db.commit()
    db.close()
    token = client.post("/auth/login", json={"email": "other.vendor@example.com", "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def _client_auth(client, test_client_login):
    token = client.post("/auth/login", json={"email": test_client_login["userEmail"], "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


# --- business profile -----------------------------------------------------------


def test_new_org_profile_is_empty(client, test_vendor_login, vendor_auth_headers):
    org = client.get(f"/organizations/{test_vendor_login['userOrg']}", headers=vendor_auth_headers).json()
    assert org["orgSocials"] == {} and org["orgWebsites"] == []
    assert org["orgEin"] is None and org["orgLogoUrl"] is None


def test_vendor_fills_in_the_business_profile(client, test_vendor_login, vendor_auth_headers):
    org_id = test_vendor_login["userOrg"]
    resp = client.patch(f"/organizations/{org_id}", json={
        "orgAddress": "1 Main St, Tampa, FL 33602",
        "orgPhone": "813-555-0100",
        "orgEin": "123456789",
        "orgCountry": "us",
        "orgLogoUrl": "https://cdn.example.com/logo.png",
        "orgSocials": {"instagram": "https://instagram.com/madrascatering"},
        "orgWebsites": ["https://madrascatering.com"],
    }, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text

    org = client.get(f"/organizations/{org_id}", headers=vendor_auth_headers).json()
    assert org["orgEin"] == "12-3456789"  # stored in one format
    assert org["orgCountry"] == "US"
    assert org["orgSocials"] == {"instagram": "https://instagram.com/madrascatering"}
    assert org["orgWebsites"] == ["https://madrascatering.com"]
    assert org["orgAddress"] == "1 Main St, Tampa, FL 33602"


@pytest.mark.parametrize("field, value", [
    ("orgEin", "12-34"),
    ("orgCountry", "USA"),
    ("orgLogoUrl", "not a url"),
    ("orgWebsites", ["madrascatering.com"]),  # needs http(s)://
    ("orgSocials", {"instagram": "ftp://example.com"}),
    ("orgWebsites", None),  # send [] to clear
    ("orgSocials", None),
])
def test_invalid_profile_values_are_rejected(client, test_vendor_login, vendor_auth_headers, field, value):
    resp = client.patch(f"/organizations/{test_vendor_login['userOrg']}", json={field: value},
                        headers=vendor_auth_headers)
    assert resp.status_code == 422, resp.text


def test_clearing_profile_fields(client, test_vendor_login, vendor_auth_headers):
    org_id = test_vendor_login["userOrg"]
    client.patch(f"/organizations/{org_id}", json={"orgWebsites": ["https://a.com"], "orgEin": "123456789"},
                 headers=vendor_auth_headers)
    resp = client.patch(f"/organizations/{org_id}", json={"orgWebsites": [], "orgEin": None},
                        headers=vendor_auth_headers)
    assert resp.json()["orgWebsites"] == [] and resp.json()["orgEin"] is None


# --- rate card --------------------------------------------------------------------


def _service(client, headers, **overrides):
    body = {"name": "Bartender", "price": "45.00", "pricingUnit": "hour", "category": "Staffing"} | overrides
    resp = client.post("/rate-card", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_rate_card_crud(client, vendor_auth_headers):
    item = _service(client, vendor_auth_headers, hours="4")
    assert (item["price"], item["pricingUnit"], item["hours"], item["active"]) == (45.0, "hour", 4.0, True)

    resp = client.patch(f"/rate-card/{item['id']}", json={"price": "50", "active": False},
                        headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    saved = client.get(f"/rate-card/{item['id']}", headers=vendor_auth_headers).json()
    assert saved["price"] == 50.0 and saved["active"] is False

    assert client.delete(f"/rate-card/{item['id']}", headers=vendor_auth_headers).status_code == 204
    assert client.get(f"/rate-card/{item['id']}", headers=vendor_auth_headers).status_code == 404


def test_rate_card_list_filters_and_sorts(client, vendor_auth_headers):
    _service(client, vendor_auth_headers, name="Waiter", price="30", category="Staffing")
    _service(client, vendor_auth_headers, name="Dosa Station", price="12", pricingUnit="guest", category="Live Stations")
    _service(client, vendor_auth_headers, name="Old Service", price="5", pricingUnit="event", category="Rentals", active=False)

    def names(query=""):
        return [i["name"] for i in client.get(f"/rate-card{query}", headers=vendor_auth_headers).json()["items"]]

    assert names() == ["Dosa Station", "Old Service", "Waiter"]  # by name
    assert names("?active=true&sort=-price") == ["Waiter", "Dosa Station"]
    assert names("?category=Staffing") == ["Waiter"]
    assert names("?search=dosa") == ["Dosa Station"]


@pytest.mark.parametrize("body", [
    {"pricingUnit": "week"},
    {"price": "-1"},
    {"hours": "0"},
    {"name": ""},
])
def test_invalid_rate_card_items_are_rejected(client, vendor_auth_headers, body):
    full = {"name": "Bartender", "price": "45", "pricingUnit": "hour"} | body
    assert client.post("/rate-card", json=full, headers=vendor_auth_headers).status_code == 422


@pytest.mark.parametrize("field", ["name", "price", "pricingUnit", "active"])
def test_required_rate_card_fields_cant_be_nulled(client, vendor_auth_headers, field):
    item = _service(client, vendor_auth_headers)
    resp = client.patch(f"/rate-card/{item['id']}", json={field: None}, headers=vendor_auth_headers)
    assert resp.status_code == 422, resp.text


# --- equipment ----------------------------------------------------------------------


def test_equipment_crud(client, vendor_auth_headers):
    resp = client.post("/equipment", json={"name": "Chafing dish", "amount": "25"}, headers=vendor_auth_headers)
    assert resp.status_code == 200, resp.text
    item = resp.json()
    assert (item["amount"], item["active"]) == (25.0, True)

    client.patch(f"/equipment/{item['id']}", json={"amount": "30.50"}, headers=vendor_auth_headers)
    assert client.get(f"/equipment/{item['id']}", headers=vendor_auth_headers).json()["amount"] == 30.5

    listed = client.get("/equipment?search=chafing", headers=vendor_auth_headers).json()
    assert [e["id"] for e in listed["items"]] == [item["id"]]

    assert client.delete(f"/equipment/{item['id']}", headers=vendor_auth_headers).status_code == 204
    assert client.get(f"/equipment/{item['id']}", headers=vendor_auth_headers).status_code == 404


def test_equipment_amount_cant_be_negative(client, vendor_auth_headers):
    resp = client.post("/equipment", json={"name": "Tent", "amount": "-5"}, headers=vendor_auth_headers)
    assert resp.status_code == 422


# --- each organization only sees its own -------------------------------------------


def test_another_org_cant_see_or_change_the_catalog(client, vendor_auth_headers, other_vendor):
    service = _service(client, vendor_auth_headers)
    equipment = client.post("/equipment", json={"name": "Tent", "amount": "100"}, headers=vendor_auth_headers).json()

    assert client.get("/rate-card", headers=other_vendor).json()["total"] == 0
    assert client.get("/equipment", headers=other_vendor).json()["total"] == 0
    for path in (f"/rate-card/{service['id']}", f"/equipment/{equipment['id']}"):
        assert client.get(path, headers=other_vendor).status_code == 404
        assert client.patch(path, json={"name": "Taken"}, headers=other_vendor).status_code == 404
        assert client.delete(path, headers=other_vendor).status_code == 404
    # untouched
    assert client.get(f"/rate-card/{service['id']}", headers=vendor_auth_headers).json()["name"] == "Bartender"


def test_clients_cant_use_the_catalog(client, test_client_login, vendor_auth_headers):
    auth = _client_auth(client, test_client_login)
    for path in ("/rate-card", "/equipment"):
        assert client.get(path, headers=auth).status_code == 403
        assert client.post(path, json={}, headers=auth).status_code in (403, 422)


def test_price_tiers_table_is_gone(engine):
    # replaced by the rate card (BE-29)
    from sqlalchemy import inspect

    assert "price_tiers" not in inspect(engine).get_table_names()
