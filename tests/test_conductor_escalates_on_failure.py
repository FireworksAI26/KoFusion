import pytest
from kovafusion.config import Settings
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest, TestFile, TestSpec

BAD = '{"files":[{"path":"main.py","content":"def add(a,b):\\n    return a-b\\n"}],"notes":"bad"}'
PATCH_BAD = '{"patch":"--- a/main.py\\n+++ b/main.py\\n@@ -1,2 +1,2 @@\\n def add(a,b):\\n-    return a-b\\n+    return a-b\\n","rationale":"still bad"}'

class FakePool:
    async def complete(self, model, prompt, *, purpose="completion"):
        assert model != "openai/gpt-5.5-pro"
        if purpose == "thinker":
            return "spec"
        if purpose == "debug_patch":
            return PATCH_BAD
        return BAD

@pytest.mark.asyncio
async def test_conductor_tries_gpt55_after_worker_failures_but_not_pro(tmp_path):
    tests = TestSpec(language="python", files=[TestFile(path="test_main.py", content="from main import add\ndef test_add(): assert add(1,2)==3\n")], run="python -m pytest -q", timeout_sec=20)
    resp = await Orchestrator(Settings(None, "default", None, tmp_path, 20, 1, False, 2.0), FakePool()).run(KovaRequest(prompt="write add", tests=tests, mode="verifiable"))
    assert "openai/gpt-5.5" in resp.models_called
    assert resp.models_called.count("openai/gpt-5.5") >= 2  # thinker plus worker attempt
    assert "openai/gpt-5.5-pro" not in resp.models_called
