"""Route-level (HTTP) API tests.

Exercise the FastAPI endpoints end-to-end through the TestClient, including
the contract from the README / capstone.yaml: HTTP status codes, enum
validation on query params, read-only GET behaviour, and the optional
ADMIN_API_KEY guard.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _decode(resp):
    return resp.status_code, (resp.json() if resp.content else None)


# --- Health ---
def test_health_ok(client: TestClient):
    code, body = _decode(client.get("/health"))
    assert code == 200
    assert body["status"] == "ok"
    assert "use_real_ai" in body
    assert "similarity_threshold" in body


# --- Images ---
def test_images_list_and_enum_filter(client: TestClient, make_image):
    make_image("fox")
    code, body = _decode(client.get("/images"))
    assert code == 200
    assert body["total"] >= 1

    # Valid enum value filters cleanly.
    code, body = _decode(client.get("/images?status_filter=COMPLETED"))
    assert code == 200

    # Invalid enum value must be a clean 422, never 500.
    code, _ = _decode(client.get("/images?status_filter=NOT_A_STATUS"))
    assert code == 422

    # Invalid pagination bounds -> 422.
    code, _ = _decode(client.get("/images?limit=0"))
    assert code == 422


def test_create_and_get_image(client: TestClient):
    code, newimg = _decode(client.post("/images", json={"filename": "rt_01.jpg"}))
    assert code == 201
    code, got = _decode(client.get(f"/images/{newimg['id']}"))
    assert code == 200
    assert got["filename"] == "rt_01.jpg"


def test_get_missing_image_404(client: TestClient):
    assert client.get("/images/does_not_exist").status_code == 404


# --- Posts ---
def test_create_list_get_post(client: TestClient, make_image):
    make_image("wolf", confidence=0.96)
    code, newpost = _decode(
        client.post("/posts", json={"title": "RT Wolves", "content": "Canines.", "category": "wolf"})
    )
    assert code == 201

    code, body = _decode(client.get("/posts"))
    assert code == 200
    assert body["total"] >= 1

    code, got = _decode(client.get(f"/posts/{newpost['id']}"))
    assert code == 200
    assert got["title"] == "RT Wolves"


def test_create_post_validation_422(client: TestClient):
    # Missing required title/content -> 422.
    assert client.post("/posts", json={}).status_code == 422


# --- Matching (read-only GET preserves state) ---
def test_match_recommend(client: TestClient, make_image, make_post):
    make_image("fox", confidence=0.96)
    post = make_post("RT Foxes", "Red foxes are wild predators with orange fur.", "fox")
    code, msg = _decode(client.post(f"/posts/{post.id}/match"))
    assert code == 200
    assert msg["decision"] in ("RECOMMENDED", "NO_CONFIDENT_MATCH")


def test_candidate_images_get_is_read_only(client: TestClient, make_image, make_post):
    """GET /posts/{id}/images must not persist suggestions (read-only)."""
    make_image("fox", confidence=0.96)
    post = make_post("RT Fox Readonly", "Red foxes live in forests.", "fox")
    code, candidates = _decode(client.get(f"/posts/{post.id}/images"))
    assert code == 200
    # Read-only: no stored suggestion should be produced by a GET.
    for c in candidates:
        assert c["suggestion_id"] is None


def test_match_missing_post_404(client: TestClient):
    assert client.post("/posts/nope/match").status_code == 404


# --- Suggestions / Reviews ---
def test_review_workflow(client: TestClient, make_image, make_post):
    make_image("dog", confidence=0.96)
    post = make_post("RT Dogs", "Dogs are loyal domestic pets.", "dog")
    code, msg = _decode(client.post(f"/posts/{post.id}/match"))
    assert code == 200
    sug_id = next((c["suggestion_id"] for c in msg["candidates"] if c["suggestion_id"]), None)
    if sug_id:
        code, rev = _decode(
            client.post(f"/suggestions/{sug_id}/approve", json={"decision": "APPROVED", "reviewer": "tester"})
        )
        assert code == 200
        assert rev["decision"] == "APPROVED"

    code, _ = _decode(client.get(f"/suggestions?post_id={post.id}"))
    assert code == 200
    code, _ = _decode(client.get("/reviews"))
    assert code == 200


def test_suggestions_invalid_decision_422(client: TestClient):
    # decision query param only accepts guard decisions.
    code, _ = _decode(client.get("/suggestions?decision=NOT_A_DECISION"))
    assert code == 422


def test_approve_missing_suggestion_404(client: TestClient):
    code, _ = _decode(client.post("/suggestions/nope/approve", json={"decision": "APPROVED"}))
    assert code == 404


# --- Evaluation & usage ---
def test_evaluation_and_usage_endpoints(client: TestClient):
    code, body = _decode(client.post("/evaluation/run"))
    assert code == 200
    assert "top1_precision" in body

    code, _ = _decode(client.get("/evaluation/latest"))
    assert code == 200

    code, usage = _decode(client.get("/usage"))
    assert code == 200
    assert "total_calls" in usage


# --- Admin key guard (only enforced when ADMIN_API_KEY is set) ---
def test_admin_key_guard_enforced_when_configured(monkeypatch, client: TestClient):
    import app.core.security as security

    monkeypatch.setenv("ADMIN_API_KEY", "secret-key")
    # require_api_key reads os.getenv at call time.
    code, _ = _decode(client.post("/evaluation/run"))
    # Without the header -> 401 when a key is configured.
    assert code == 401
    code, _ = _decode(
        client.post("/evaluation/run", headers={"X-API-Key": "wrong-key"})
    )
    assert code == 401
    code, _ = _decode(
        client.post("/evaluation/run", headers={"X-API-Key": "secret-key"})
    )
    assert code == 200
