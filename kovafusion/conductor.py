from __future__ import annotations

import json, time, uuid
from dataclasses import dataclass
from typing import Any, Literal

from .config import Settings
from .pool import GPT55, GPT55_PRO, ModelPool, CostGovernor, WORKER_MODELS
from .prompts import thinker_prompt, worker_prompt, debugger_prompt, judge_prompt
from .repair import extract_json_block, files_from_model_output, apply_unified_diff
from .schemas import KovaRequest, KovaResponse, VerifierResult
from .select import choose_candidate, candidates_differ
from .verifier import run_verifier


def _ms() -> int:
    return int(time.time() * 1000)


def _truncate(value: Any, limit: int = 1200) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


@dataclass(frozen=True)
class ConductorAction:
    type: Literal["plan", "spawn_candidate", "verify_candidate", "debug_patch", "apply_patch", "escalate", "synthesize", "stop"]
    candidate_id: str | None = None
    model: str | None = None
    reason: str = ""


class Conductor:
    def __init__(self, settings: Settings, pool: ModelPool):
        self.settings = settings
        self.pool = pool

    async def _call(self, model: str, prompt: str, purpose: str, trace: dict[str, Any], governor: CostGovernor) -> str:
        if len(trace["models_called"]) >= self.settings.max_models_per_request:
            raise RuntimeError("model call limit exceeded")
        if not governor.can_call(model):
            trace.setdefault("escalation_decisions", []).append({"model": model, "trigger": purpose, "allowed": False, "reason": "governor blocked"})
            raise RuntimeError(f"cost governor blocked {model}")
        started = _ms()
        try:
            return await self.pool.complete(model, prompt, purpose=purpose)
        finally:
            trace["models_called"].append(model)
            trace["model_calls"].append({"model": model, "purpose": purpose, "started_ms": started, "ended_ms": _ms()})
            trace["cost_governor"] = governor.decisions

    def _step(self, trace: dict[str, Any], action: ConductorAction, inputs: Any = None, outputs: Any = None) -> None:
        trace.setdefault("conductor_steps", []).append({
            "index": len(trace.setdefault("conductor_steps", [])) + 1,
            "action": action.type,
            "model": action.model,
            "candidate_id": action.candidate_id,
            "reason": action.reason,
            "inputs_summary": _truncate(inputs),
            "outputs_summary": _truncate(outputs),
        })

    def _new_candidate(self, model: str, files: list[dict[str, str]], notes: str, raw: str) -> dict[str, Any]:
        cid = uuid.uuid4().hex[:10]
        return {"id": cid, "model": model, "files": files, "notes": notes, "repairs_used": 0, "raw": raw, "lineage": [{"revision": 0, "event": "spawn", "files": files}]}

    async def run_verifiable(self, req: KovaRequest, trace: dict[str, Any], governor: CostGovernor) -> KovaResponse:
        assert req.tests is not None
        spec = await self._plan(req, trace, governor)
        candidates: list[dict[str, Any]] = []

        for model in WORKER_MODELS:
            candidates.append(await self._spawn(req, spec, model, trace, governor))
            await self._verify(candidates[-1], req, trace)
            if candidates[-1]["verifier"]["passed"] and candidates[-1]["repairs_used"] == 0:
                return await self._finish(req, spec, candidates, trace, governor, "early pass with no repairs")

        for cand in candidates:
            if not cand["verifier"]["passed"]:
                await self._debug_apply_verify(req, spec, cand, trace, governor)
                if cand["verifier"]["passed"] and cand["repairs_used"] == 1:
                    # Stop once evidence shows a repaired cheap worker passes.
                    return await self._finish(req, spec, candidates, trace, governor, "cheap worker passed after one patch")

        if not any(c["verifier"]["passed"] for c in candidates):
            trace.setdefault("escalation_decisions", []).append({"trigger": "no pass after one repair", "model": GPT55, "allowed": True, "reason": "try ceiling non-pro worker"})
            gpt_cand = await self._spawn(req, spec, GPT55, trace, governor)
            await self._verify(gpt_cand, req, trace)
            candidates.append(gpt_cand)
            if not gpt_cand["verifier"]["passed"]:
                await self._debug_apply_verify(req, spec, gpt_cand, trace, governor)

        if self._needs_pro(candidates):
            allowed = self.settings.enable_gpt55_pro and governor.can_call(GPT55_PRO)
            trace.setdefault("escalation_decisions", []).append({"trigger": "still no pass or critical conflict", "model": GPT55_PRO, "allowed": allowed, "reason": "enabled and under cap" if allowed else "disabled or over cap"})
            if allowed and len(trace["models_called"]) < self.settings.max_models_per_request:
                pro_cand = await self._spawn(req, spec, GPT55_PRO, trace, governor, charge_already_reserved=True)
                await self._verify(pro_cand, req, trace)
                candidates.append(pro_cand)
            trace["cost_governor"] = governor.decisions

        return await self._finish(req, spec, candidates, trace, governor, "selection after adaptive loop")

    async def _plan(self, req: KovaRequest, trace: dict[str, Any], governor: CostGovernor) -> str:
        action = ConductorAction("plan", model=GPT55, reason="create spec and test strategy")
        prompt = thinker_prompt(req.prompt, req.tests.model_dump() if req.tests else None)
        spec = await self._call(GPT55, prompt, "thinker", trace, governor)
        self._step(trace, action, {"prompt": req.prompt}, spec)
        return spec

    async def _spawn(self, req: KovaRequest, spec: str, model: str, trace: dict[str, Any], governor: CostGovernor, charge_already_reserved: bool = False) -> dict[str, Any]:
        action = ConductorAction("spawn_candidate", model=model, reason="produce strict JSON files candidate")
        prompt = worker_prompt(req.prompt, spec)
        if charge_already_reserved:
            # Avoid double-charging the pro preflight decision while still making a real traced call.
            output = await self.pool.complete(model, prompt, purpose="candidate")
            trace["models_called"].append(model)
            trace["model_calls"].append({"model": model, "purpose": "candidate", "started_ms": _ms(), "ended_ms": _ms()})
        else:
            output = await self._call(model, prompt, "candidate", trace, governor)
        files, notes = files_from_model_output(output)
        cand = self._new_candidate(model, files, notes, output)
        self._step(trace, action, {"model": model}, {"candidate_id": cand["id"], "notes": notes, "files": [f["path"] for f in files]})
        return cand

    async def _verify(self, cand: dict[str, Any], req: KovaRequest, trace: dict[str, Any]) -> VerifierResult:
        action = ConductorAction("verify_candidate", candidate_id=cand["id"], reason="run local verifier")
        result = await run_verifier(cand["files"], req.tests)  # type: ignore[arg-type]
        cand["verifier"] = result.model_dump()
        cand["lineage"].append({"revision": len(cand["lineage"]), "event": "verify", "result": cand["verifier"]})
        self._step(trace, action, {"files": [f["path"] for f in cand["files"]]}, cand["verifier"])
        return result

    async def _debug_apply_verify(self, req: KovaRequest, spec: str, cand: dict[str, Any], trace: dict[str, Any], governor: CostGovernor) -> None:
        if cand["repairs_used"] >= self.settings.max_repairs_per_candidate:
            return
        verifier = cand["verifier"]
        prompt = debugger_prompt(req.prompt, spec, cand["files"], verifier.get("stdout", ""), verifier.get("stderr", ""))
        action = ConductorAction("debug_patch", candidate_id=cand["id"], model=cand["model"], reason="minimal patch from verifier evidence")
        raw = await self._call(cand["model"], prompt, "debug_patch", trace, governor)
        data = extract_json_block(raw)
        patch = data.get("patch", "")
        rationale = data.get("rationale", "")
        self._step(trace, action, {"verifier": verifier}, {"rationale": rationale, "patch": patch})

        apply_action = ConductorAction("apply_patch", candidate_id=cand["id"], reason="deterministic unified diff application")
        cand["files"] = apply_unified_diff(cand["files"], patch)
        cand["repairs_used"] += 1
        cand["lineage"].append({"revision": len(cand["lineage"]), "event": "patch", "patch": patch, "rationale": rationale, "files": cand["files"]})
        self._step(trace, apply_action, patch, {"repairs_used": cand["repairs_used"], "files": [f["path"] for f in cand["files"]]})
        await self._verify(cand, req, trace)

    def _needs_pro(self, candidates: list[dict[str, Any]]) -> bool:
        passing = [c for c in candidates if c.get("verifier", {}).get("passed")]
        if not passing:
            return True
        return len(passing) > 1 and candidates_differ(passing)

    async def _finish(self, req: KovaRequest, spec: str, candidates: list[dict[str, Any]], trace: dict[str, Any], governor: CostGovernor, reason: str) -> KovaResponse:
        winner, selection_reason = choose_candidate(candidates)
        passing = [c for c in candidates if c.get("verifier", {}).get("passed")]
        if len(passing) > 1 and candidates_differ(passing):
            # Evidence-driven tie-breaker: ask judge only after verifier has narrowed to passing candidates.
            summary = [{"id": c["id"], "model": c["model"], "repairs_used": c["repairs_used"], "verifier": c["verifier"], "files": c["files"]} for c in passing]
            try:
                raw = await self._call(GPT55, judge_prompt(req.prompt, spec, summary), "judge", trace, governor)
                data = extract_json_block(raw)
                judged = next((c for c in passing if c["id"] == data.get("winner_id")), None)
                if judged:
                    winner = judged
                    selection_reason = "judge tie-breaker: " + str(data.get("reason", ""))
            except Exception as exc:  # keep deterministic fallback
                selection_reason += f"; judge unavailable, used deterministic tie-breaker: {exc}"
        trace["candidates"] = candidates
        trace["candidate_lineage"] = [{"id": c["id"], "model": c["model"], "lineage": c["lineage"]} for c in candidates]
        trace["final_selection_reason"] = selection_reason
        action = ConductorAction("synthesize", candidate_id=winner["id"], reason=reason)
        answer = json.dumps({"files": winner["files"], "notes": winner.get("notes", ""), "selection_reason": selection_reason}, indent=2, sort_keys=True)
        self._step(trace, action, {"candidates": len(candidates)}, {"winner": winner["id"], "verified": winner["verifier"]["passed"]})
        self._step(trace, ConductorAction("stop", candidate_id=winner["id"], reason=reason), None, {"verified": winner["verifier"]["passed"]})
        return KovaResponse(answer=answer, verified=winner["verifier"]["passed"], verifier=winner["verifier"], trace_id=trace["trace_id"], models_called=trace["models_called"], repairs_used=winner.get("repairs_used", 0))
