from __future__ import annotations

import asyncio
import time
from pathlib import Path

from kovafusion.config import get_settings
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest, TestFile, TestSpec


async def _run_case(orchestrator: Orchestrator, name: str, req: KovaRequest) -> dict:
    started = time.perf_counter()
    try:
        response = await orchestrator.run(req)
        return {
            "name": name,
            "ok": True,
            "verified": response.verified,
            "models_called": len(response.models_called),
            "models": ", ".join(response.models_called),
            "repairs_used": response.repairs_used,
            "trace_id": response.trace_id,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": "",
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "verified": False,
            "models_called": 0,
            "models": "",
            "repairs_used": 0,
            "trace_id": "",
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": repr(exc),
        }


async def main() -> None:
    settings = get_settings()
    orchestrator = Orchestrator(settings)
    tests = TestSpec(
        language="python",
        files=[TestFile(path="test_main.py", content="from main import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")],
        run="python -m pytest -q",
        timeout_sec=20,
    )
    cases = [
        ("kova-atlas-nonverifiable", KovaRequest(prompt="Explain why adaptive model fusion can improve answer reliability in five bullet points.", mode="nonverifiable", profile="standard")),
        ("kova-atlas-ultra-nonverifiable", KovaRequest(prompt="Compare multi-model answer synthesis with conductor-style orchestration.", mode="nonverifiable", profile="ultra")),
        ("kova-atlas-verifiable-python", KovaRequest(prompt="Write main.py that defines add(a, b) and returns the numeric sum.", mode="verifiable", tests=tests, profile="standard")),
    ]
    rows = [await _run_case(orchestrator, name, req) for name, req in cases]
    passed = sum(1 for row in rows if row["ok"] and (row["verified"] or "nonverifiable" in row["name"]))
    total_models = sum(row["models_called"] for row in rows)
    report = [
        "# Cloudflare KovaFusion Benchmark Report",
        "",
        f"Generated with trace dir `{settings.trace_dir}`.",
        "",
        "| case | ok | verified | models_called | repairs | duration_ms | trace_id | error |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        report.append(
            f"| {row['name']} | {row['ok']} | {row['verified']} | {row['models_called']} | {row['repairs_used']} | {row['duration_ms']} | {row['trace_id']} | {row['error']} |"
        )
    report.extend([
        "",
        "## Summary",
        "",
        f"- pass_or_success_rate: {passed}/{len(rows)}",
        f"- avg_models_called: {total_models / max(len(rows), 1):.2f}",
        "- profile coverage: **Kova Atlas** (`kova-atlas`) and **Kova Atlas Ultra** (`kova-atlas-ultra`)",
        "",
        "## Model calls",
        "",
    ])
    for row in rows:
        report.append(f"- {row['name']}: {row['models'] or 'none'}")
    out = Path("evals/cloudflare_benchmark_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    if any(not row["ok"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
