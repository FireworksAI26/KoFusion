from __future__ import annotations

import json


def candidates_differ(candidates: list[dict]) -> bool:
    canonical = {json.dumps(c.get("files", []), sort_keys=True) for c in candidates}
    return len(canonical) > 1


def choose_candidate(candidates: list[dict]) -> tuple[dict, str]:
    passing = [c for c in candidates if c.get("verifier", {}).get("passed")]
    pool = passing or candidates
    winner = sorted(pool, key=lambda c: (not c.get("verifier", {}).get("passed", False), c.get("repairs_used", 0), c.get("verifier", {}).get("duration_ms", 10**9)))[0]
    reason = "selected passing candidate by repairs then duration" if passing else "no passing candidates; selected least-repaired fastest failure"
    return winner, reason
