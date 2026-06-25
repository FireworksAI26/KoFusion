import pytest
from kovafusion.config import Settings
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest

class FakePool:
    async def complete(self, model, prompt, *, purpose="completion"):
        if purpose == "judge":
            return '{"consensus":"ok","contradictions":[],"gaps":[],"insights":["x"]}'
        if purpose == "synth":
            return "final answer"
        return f"answer from {model}"

@pytest.mark.asyncio
async def test_smoke_nonverifiable(tmp_path):
    s = Settings(None, "default", None, tmp_path, 10, 2, False, 2.0)
    resp = await Orchestrator(s, FakePool()).run(KovaRequest(prompt="explain fusion", mode="nonverifiable"))
    assert resp.answer == "final answer"
    assert resp.verified is False
    assert resp.verifier is None
    assert len([m for m in resp.models_called if m.startswith(("workers-ai/", "openai/gpt-5.5"))]) >= 3
    assert len(set(resp.models_called[:3])) == 3
    assert (tmp_path / f"{resp.trace_id}.json").exists()
