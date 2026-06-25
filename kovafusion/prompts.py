from __future__ import annotations

import json


def thinker_prompt(task: str, tests_metadata: dict | None) -> str:
    return (
        "Role: Thinker. Produce a crisp implementation spec, constraints, and test strategy. "
        "For verifiable tasks, emphasize satisfying the provided tests without overfitting.\n"
        f"Task:\n{task}\nTests metadata:\n{json.dumps(tests_metadata or {}, sort_keys=True)}"
    )


def worker_prompt(task: str, spec: str) -> str:
    return (
        "Role: Worker. Implement the task. Return ONLY strict JSON with this schema: "
        '{"files":[{"path":"main.py","content":"..."}],"notes":"..."}. '
        "Do not include markdown fences or commentary outside JSON.\n"
        f"Task:\n{task}\nSpec:\n{spec}"
    )


def debugger_prompt(task: str, spec: str, files: list[dict[str, str]], stdout: str, stderr: str) -> str:
    return (
        "Role: Debugger. Read the verifier output and produce the smallest possible unified diff patch "
        "against the current files, plus a short rationale. Prefer minimal diffs; do not rewrite entire files unless necessary.\n"
        "Return ONLY JSON with this schema: {\"patch\":\"--- a/main.py\\n+++ b/main.py\\n@@ ...\",\"rationale\":\"...\"}.\n"
        f"Task:\n{task}\nSpec:\n{spec}\nCurrent files:\n{json.dumps(files, sort_keys=True)}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


def judge_prompt(task: str, spec: str, candidates_summary: list[dict]) -> str:
    return (
        "Role: Judge. Choose the best passing candidate using the spec and verifier evidence only. "
        "Return JSON {\"winner_id\":\"...\",\"reason\":\"...\"}. No vibes-only judging.\n"
        f"Task:\n{task}\nSpec:\n{spec}\nCandidates:\n{json.dumps(candidates_summary, sort_keys=True)}"
    )
