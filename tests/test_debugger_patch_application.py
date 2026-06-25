import pytest
from kovafusion.repair import apply_unified_diff
from kovafusion.config import Settings
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest, TestFile, TestSpec

BAD = '{"files":[{"path":"main.py","content":"def add(a,b):\\n    return a-b\\n"}],"notes":"bad"}'
PATCH = '{"patch":"--- a/main.py\\n+++ b/main.py\\n@@ -1,2 +1,2 @@\\n def add(a,b):\\n-    return a-b\\n+    return a+b\\n","rationale":"fix subtraction"}'

class FakePool:
    async def complete(self, model, prompt, *, purpose="completion"):
        if purpose == "thinker":
            return "spec"
        if purpose == "candidate":
            return BAD
        if purpose == "debug_patch":
            return PATCH
        raise AssertionError(purpose)


def test_apply_unified_diff_deterministic():
    files = [{"path": "main.py", "content": "def add(a,b):\n    return a-b\n"}]
    patch = "--- a/main.py\n+++ b/main.py\n@@ -1,2 +1,2 @@\n def add(a,b):\n-    return a-b\n+    return a+b\n"
    assert apply_unified_diff(files, patch) == [{"path": "main.py", "content": "def add(a,b):\n    return a+b\n"}]

@pytest.mark.asyncio
async def test_debugger_patch_application_allows_verifier_to_pass(tmp_path):
    tests = TestSpec(language="python", files=[TestFile(path="test_main.py", content="from main import add\ndef test_add(): assert add(4,5)==9\n")], run="python -m pytest -q", timeout_sec=20)
    resp = await Orchestrator(Settings(None, "default", None, tmp_path, 10, 2, False, 2.0), FakePool()).run(KovaRequest(prompt="write add", tests=tests, mode="verifiable"))
    assert resp.verified is True
    assert resp.repairs_used == 1
    assert "return a+b" in resp.answer
