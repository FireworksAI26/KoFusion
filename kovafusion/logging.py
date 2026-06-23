from __future__ import annotations

import json
from pathlib import Path
from typing import Any


async def write_trace(trace_dir: Path, trace_id: str, trace: dict[str, Any]) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{trace_id}.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True), encoding="utf-8")


def read_trace(trace_dir: Path, trace_id: str) -> dict[str, Any] | None:
    path = trace_dir / f"{trace_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
