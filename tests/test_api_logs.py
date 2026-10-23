from sqlalchemy import text


API = "/api/v1"  # the logged path is the full one the request used


def _logs(engine, path):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM api_logs WHERE path = :path ORDER BY occurred_at"), {"path": API + path}
        ).mappings().all()


def test_authenticated_request_is_logged(client, engine, vendor_auth_headers, test_vendor_login):
    resp = client.get("/users?limit=5", headers=vendor_auth_headers)
    assert resp.status_code == 200

    [log] = _logs(engine, "/users")
    assert log["method"] == "GET"
    assert log["route"] == API + "/users"
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


# --- BE-24: the log is written after the response, not before -------------------


def _request(path="/api/v1/projects"):
    from starlette.requests import Request

    return Request({
        "type": "http", "method": "GET", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [], "client": ("127.0.0.1", 5000),
        "server": ("testserver", 80), "scheme": "http", "root_path": "", "state": {},
    })


def _run_middleware(monkeypatch, call_next):
    """Runs the logging middleware by itself. Returns (response, rows logged
    by the time the response was ready, rows logged after its background ran)."""
    import asyncio

    import main

    written = []
    monkeypatch.setattr(main, "record_api_log", lambda **fields: written.append(fields))

    async def run():
        response = await main.log_api_activity(_request(), call_next)
        before = list(written)
        await response.background()
        return response, before, list(written)

    return asyncio.run(run())


def test_log_is_written_after_the_response_is_ready(monkeypatch):
    from starlette.responses import PlainTextResponse

    async def call_next(request):
        return PlainTextResponse("ok")

    response, before, after = _run_middleware(monkeypatch, call_next)
    assert before == []  # nothing written while the response was being produced
    [row] = after
    assert row["statusCode"] == 200
    assert str(row["requestId"]) == response.headers["X-Request-ID"]


def test_a_routes_own_background_work_still_runs(monkeypatch):
    from starlette.background import BackgroundTask
    from starlette.responses import PlainTextResponse

    ran = []

    async def call_next(request):
        return PlainTextResponse("ok", background=BackgroundTask(lambda: ran.append("route task")))

    _, _, after = _run_middleware(monkeypatch, call_next)
    assert ran == ["route task"]
    assert len(after) == 1


def test_unhandled_error_is_still_logged_as_a_500(monkeypatch):
    async def call_next(request):
        raise RuntimeError("boom")

    response, before, after = _run_middleware(monkeypatch, call_next)
    assert response.status_code == 500 and before == []
    [row] = after
    assert row["statusCode"] == 500 and "boom" in row["error"]
