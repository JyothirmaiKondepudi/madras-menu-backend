"""BE-27: every API route is under /api/v1; only the health checks are at the
root. Actions (accept, reject, read, seen, disable, enable, void, ...) are
POST."""
from main import API_PREFIX, app

ROOT_PATHS = {"/", "/db/health"}


def test_every_api_route_is_under_the_version_prefix():
    outside = [p for p in app.openapi()["paths"] if p not in ROOT_PATHS and not p.startswith(API_PREFIX + "/")]
    assert not outside, f"routes outside {API_PREFIX}: {outside}"


def test_old_unprefixed_paths_are_gone(client, vendor_auth_headers):
    resp = client.get("http://testserver/users", headers=vendor_auth_headers)
    assert resp.status_code == 404


def test_actions_are_post_not_patch():
    paths = app.openapi()["paths"]
    for suffix in ("/accept", "/reject", "/read", "/seen", "/change-password"):
        [path] = [p for p in paths if p.endswith(suffix)]
        assert set(paths[path]) == {"post"}, (path, set(paths[path]))
