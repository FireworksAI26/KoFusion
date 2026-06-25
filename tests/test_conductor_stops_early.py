import pytest
from kovafusion.config import Settings
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest, TestFile, TestSpec

GOOD = '{"files":[{"path":"main.py","content":"def add(a,b):\\n    return a+b\\n"}],"notes":"good"}'

class FakePool:
    async def complete(self, model, prompt, *, purpose="completion"):
        if purpose == "thinker":
            return "spec"
        if purpose == "candidate":
            return GOOD
        raise AssertionError(f"unexpected {purpose}")

@pytest.mark.asyncio
async def test_conductor_stops_early_when_first_worker_passes(tmp_path):
    tests = TestSpec(language="python", files=[TestFile(path="test_main.py", content="from main import add\ndef test_add(): assert add(1,2)==3\n")], run="python -m pytest -q", timeout_sec=20)
    resp = await Orchestrator(Settings(None, "default", None, tmp_path, 10, 2, False, 2.0), FakePool()).run(KovaRequest(prompt="write add", tests=tests, mode="verifiable"))
    assert resp.verified is True
    assert len(resp.models_called) == 2
    trace = (tmp_path / f"{resp.trace_id}.json").read_text()
    assert '"action": "stop"' in trace
