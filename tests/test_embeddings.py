"""
Tests here deliberately don't require Ollama to be running — they exercise
the parts that are testable without it: 404 on a nonexistent item (checked
before any Ollama call happens at all), and the graceful 503 when Ollama is
unreachable (the real, actually-observed failure mode on this machine while
this code was written — see main.py's ConnectionError handler).

Once Ollama is actually installed, add a separate test file for the real
generate -> store -> search round trip; these tests should keep passing
unchanged regardless, since they're specifically about the no-Ollama case.
"""


def test_embed_nonexistent_item_returns_404(client):
    resp = client.post("/menu-items/does-not-exist/embedding")
    assert resp.status_code == 404


def test_embed_real_item_without_ollama_returns_503(client, test_menu_item):
    resp = client.post(f"/menu-items/{test_menu_item['id']}/embedding")
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


def test_search_without_ollama_returns_503(client):
    resp = client.get("/embeddings/search", params={"text": "tamarind rice"})
    assert resp.status_code == 503
