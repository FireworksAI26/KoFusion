import pytest
from kovafusion.config import Settings
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest, TestSpec, TestFile

BAD = '{"files":[{"path":"main.py","content":"def add(a,b):\\n    return a-b\\n"}],"notes":"bad"}'
PATCH_BAD = '{"patch":"--- a/main.py\\n+++ b/main.py\\n@@ -1,2 +1,2 @@\\n def add(a,b):\\n-    return a-b\\n+    return a-b\\n","rationale":"no-op"}'

class FakePool:
    async def complete(self, model, prompt, *, purpose="completion"):
        assert model != "openai/gpt-5.5-pro"
        if purpose == "thinker":
            return "spec"
        if purpose == "debug_patch":
            return PATCH_BAD
        return BAD

@pytest.mark.asyncio
async def test_gpt55_pro_not_called_when_disabled(tmp_path):
    tests = TestSpec(language="python", files=[TestFile(path="test_main.py", content="from main import add\ndef test_add(): assert add(2,3)==5\n")], run="python -m pytest -q", timeout_sec=20)
    s = Settings(None, "default", None, tmp_path, 20, 1, False, 2.0)
    resp = await Orchestrator(s, FakePool()).run(KovaRequest(prompt="write add", tests=tests, mode="verifiable"))
    assert "openai/gpt-5.5-pro" not in resp.models_called

@pytest.mark.asyncio
async def test_gpt55_pro_not_called_when_cap_exceeded(tmp_path):
    tests = TestSpec(language="python", files=[TestFile(path="test_main.py", content="from main import add\ndef test_add(): assert add(2,3)==5\n")], run="python -m pytest -q", timeout_sec=20)
    s = Settings(None, "default", None, tmp_path, 20, 1, True, 0.50)
    resp = await Orchestrator(s, FakePool()).run(KovaRequest(prompt="write add", tests=tests, mode="verifiable"))
    assert "openai/gpt-5.5-pro" not in resp.models_called
