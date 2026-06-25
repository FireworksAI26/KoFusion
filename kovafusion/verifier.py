from __future__ import annotations

import asyncio, time, os
from pathlib import Path
from tempfile import TemporaryDirectory
from .schemas import TestSpec, VerifierResult


async def run_verifier(files: list[dict[str, str]], tests: TestSpec) -> VerifierResult:
    start = time.perf_counter()
    with TemporaryDirectory() as td:
        root = Path(td)
        for item in files:
            p = root / item["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(item["content"], encoding="utf-8")
        for tf in tests.files:
            p = root / tf.path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(tf.content, encoding="utf-8")
        try:
            proc = await asyncio.create_subprocess_shell(
                tests.run,
                cwd=root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=tests.timeout_sec)
            code = proc.returncode or 0
        except asyncio.TimeoutError:
            proc.kill()
            stdout_b, stderr_b = await proc.communicate()
            code = 124
        duration = int((time.perf_counter() - start) * 1000)
        return VerifierResult(passed=code == 0, stdout=stdout_b.decode(errors="replace"), stderr=stderr_b.decode(errors="replace"), exit_code=code, duration_ms=duration)
