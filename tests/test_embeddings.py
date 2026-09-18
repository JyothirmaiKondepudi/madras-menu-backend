"""
The Ollama-unavailable tests use a mock, deliberately — not "just don't run
Ollama locally." A test suite shouldn't pass or fail based on whether the
person/CI running it happens to have Ollama up; mocking generate_embedding
to raise makes the failure path deterministic regardless of environment.

The real round-trip tests actually call Ollama for real (this machine has
nomic-embed-text pulled and running) and are skipped, not failed, if it's
unreachable — e.g. in CI, which won't have a local Ollama daemon.
"""

import socket
from unittest.mock import patch

import pytest


def _ollama_reachable() -> bool:
    try:
        with socket.create_connection(("localhost", 11434), timeout=0.5):
            return True
    except OSError:
        return False


OLLAMA_AVAILABLE = _ollama_reachable()


def test_embed_nonexistent_item_returns_404(client):
    resp = client.post("/menu-items/does-not-exist/embedding")
    assert resp.status_code == 404


def test_embed_ollama_connection_error_returns_503(client, test_menu_item):
    with patch("embeddings.service.generate_embedding", side_effect=ConnectionError("Ollama down")):
        resp = client.post(f"/menu-items/{test_menu_item['id']}/embedding")
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


def test_search_ollama_connection_error_returns_503(client):
    with patch("embeddings.service.generate_embedding", side_effect=ConnectionError("Ollama down")):
        resp = client.get("/embeddings/search", params={"text": "tamarind rice"})
    assert resp.status_code == 503


@pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Ollama isn't running locally")
def test_embed_and_search_real_round_trip(client, test_menu_item):
    """The actual thing this whole feature is for: generate a real
    embedding via Ollama, store it, then find it again by semantic search
    on its own name."""
    embed_resp = client.post(f"/menu-items/{test_menu_item['id']}/embedding")
    assert embed_resp.status_code == 200, embed_resp.text
    assert embed_resp.json()["itemId"] == test_menu_item["id"]

    search_resp = client.get(
        "/embeddings/search", params={"text": test_menu_item["name"], "limit": 1}
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) == 1
    assert results[0]["itemId"] == test_menu_item["id"]
