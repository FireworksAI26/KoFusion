from fastapi.testclient import TestClient
import app as app_module
from kovafusion.schemas import KovaResponse


class FakeOrchestrator:
    def __init__(self, settings):
        self.settings = settings

    async def run(self, req):
        assert "user: hello fusion" in req.prompt
        self.profile = req.profile
        return KovaResponse(
            answer="hello from kovafusion",
            verified=False,
            verifier=None,
            trace_id="trace123",
            models_called=["workers-ai/@cf/moonshotai/kimi-k2.7-code"],
            repairs_used=0,
        )


def test_openai_chat_completions_shape(monkeypatch):
    monkeypatch.setattr(app_module, "Orchestrator", FakeOrchestrator)
    client = TestClient(app_module.app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "kova-atlas", "messages": [{"role": "user", "content": "hello fusion"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "kova-atlas"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "hello from kovafusion"
    assert data["kovafusion"]["trace_id"] == "trace123"


def test_openai_chat_completions_ultra_profile(monkeypatch):
    seen = {}

    class UltraFakeOrchestrator(FakeOrchestrator):
        async def run(self, req):
            seen["profile"] = req.profile
            return await super().run(req)

    monkeypatch.setattr(app_module, "Orchestrator", UltraFakeOrchestrator)
    client = TestClient(app_module.app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "kova-atlas-ultra", "messages": [{"role": "user", "content": "hello fusion"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["model"] == "kova-atlas-ultra"
    assert seen["profile"] == "ultra"
