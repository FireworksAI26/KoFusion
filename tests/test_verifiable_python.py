import pytest
from kovafusion.config import Settings
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest, TestSpec, TestFile

BAD = '{"files":[{"path":"main.py","content":"def add(a,b):\\n    return a-b\\n"}],"notes":"bad"}'
GOOD = '{"files":[{"path":"main.py","content":"def add(a,b):\\n    return a+b\\n"}],"notes":"good"}'
PATCH = '{"patch":"--- a/main.py\\n+++ b/main.py\\n@@ -1,2 +1,2 @@\\n def add(a,b):\\n-    return a-b\\n+    return a+b\\n","rationale":"fix operator"}'

class FakePool:
    async def complete(self, model, prompt, *, purpose="completion"):
        if purpose == "thinker":
            return "implement add"
        if purpose == "candidate":
            return BAD if "kimi" in model else GOOD
        if purpose == "debug_patch":
            return PATCH
        raise AssertionError(purpose)

@pytest.mark.asyncio
async def test_verifiable_python_repair_selection(tmp_path):
    tests = TestSpec(language="python", files=[TestFile(path="test_main.py", content="from main import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")], run="python -m pytest -q", timeout_sec=20)
    s = Settings(None, "default", None, tmp_path, 10, 2, False, 2.0)
    resp = await Orchestrator(s, FakePool()).run(KovaRequest(prompt="write add(a,b)", tests=tests, mode="verifiable"))
    assert resp.verified is True
    assert resp.verifier.passed is True
    assert resp.repairs_used in (0, 1)
    assert "return a+b" in resp.answer
