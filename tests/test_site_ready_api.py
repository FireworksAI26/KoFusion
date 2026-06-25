from fastapi.testclient import TestClient
import app as app_module


def test_healthz_and_models_for_site():
    client = TestClient(app_module.app)
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    models = client.get("/v1/models")
    assert models.status_code == 200
    ids = [item["id"] for item in models.json()["data"]]
    assert ids == ["kova-atlas", "kova-atlas-ultra"]


def test_cors_preflight_for_site():
    client = TestClient(app_module.app)
    resp = client.options(
        "/v1/chat/completions",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"
