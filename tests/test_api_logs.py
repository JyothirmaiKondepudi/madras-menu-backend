from sqlalchemy import text


def _logs(engine, path):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM api_logs WHERE path = :path ORDER BY occurred_at"), {"path": path}
        ).mappings().all()


def test_authenticated_request_is_logged(client, engine, vendor_auth_headers, test_vendor_login):
    resp = client.get("/users?limit=5", headers=vendor_auth_headers)
    assert resp.status_code == 200

    [log] = _logs(engine, "/users")
    assert log["method"] == "GET"
    assert log["route"] == "/users"
    assert log["status_code"] == 200
    assert str(log["user_id"]) == test_vendor_login["userId"]
    assert log["query_params"] == {"limit": "5"}
    assert log["duration_ms"] >= 0


def test_unauthenticated_request_is_logged_without_user(client, engine):
    assert client.get("/users").status_code == 401

    [log] = _logs(engine, "/users")
    assert log["status_code"] == 401
    assert log["user_id"] is None
    assert log["query_params"] is None


def test_unknown_path_is_logged_without_route(client, engine):
    assert client.get("/does-not-exist").status_code == 404

    [log] = _logs(engine, "/does-not-exist")
    assert log["status_code"] == 404
    assert log["route"] is None


def test_request_id_header_matches_log(client, engine, vendor_auth_headers):
    resp = client.get("/users", headers=vendor_auth_headers)

    [log] = _logs(engine, "/users")
    assert resp.headers["X-Request-ID"] == str(log["request_id"])


def test_deleting_user_keeps_their_logs(client, engine, vendor_auth_headers, test_client_login):
    client_id = test_client_login["userId"]
    token = client.post("/auth/login", json={
        "email": "login.client@example.com",
        "password": "correct-horse-battery-staple",
    }).json()["access_token"]
    client.get(f"/users/{client_id}", headers={"Authorization": f"Bearer {token}"})

    # user_id is ON DELETE SET NULL, so the delete succeeds and the row survives
    assert client.delete(f"/users/{client_id}", headers=vendor_auth_headers).status_code == 204
    [log] = _logs(engine, f"/users/{client_id}")[:1]
    assert log["user_id"] is None
