from __future__ import annotations

import asyncio, json, time, uuid
from typing import Any

from .config import Settings
from .logging import write_trace
from .pool import DEFAULT_FANOUT, GPT55, GPT55_PRO, CostGovernor, ModelPool, WORKER_MODELS
from .conductor import Conductor
from .repair import build_repair_prompt, files_from_model_output
from .schemas import KovaRequest, KovaResponse
from .select import choose_candidate
from .verifier import run_verifier


def _now_ms() -> int:
    return int(time.time() * 1000)


class Orchestrator:
    def __init__(self, settings: Settings, pool: ModelPool | None = None):
        self.settings = settings
        self.pool = pool or ModelPool(settings)

    async def _call(self, model: str, prompt: str, purpose: str, trace: dict[str, Any], governor: CostGovernor) -> str:
        if len(trace["models_called"]) >= self.settings.max_models_per_request:
            raise RuntimeError("model call limit exceeded")
        if not governor.can_call(model):
            trace["cost_governor"] = governor.decisions
            raise RuntimeError(f"cost governor blocked {model}")
        started = _now_ms()
        try:
            output = await self.pool.complete(model, prompt, purpose=purpose)
            return output
        finally:
            trace["models_called"].append(model)
            trace["model_calls"].append({"model": model, "purpose": purpose, "started_ms": started, "ended_ms": _now_ms()})
            trace["cost_governor"] = governor.decisions

    async def run(self, req: KovaRequest) -> KovaResponse:
        trace_id = uuid.uuid4().hex
        trace: dict[str, Any] = {"trace_id": trace_id, "prompt": req.prompt, "mode": req.mode, "profile": req.profile, "tests": req.tests.model_dump() if req.tests else None, "models_called": [], "model_calls": [], "candidates": [], "repair_prompts": [], "cost_governor": []}
        governor = CostGovernor(self.settings)
        try:
            if req.mode == "verifiable" or (req.mode == "auto" and req.tests is not None):
                response = await Conductor(self.settings, self.pool).run_verifiable(req, trace, governor)
            else:
                response = await self._nonverifiable(req, trace, governor)
            trace["response"] = response.model_dump()
            return response
        finally:
            await write_trace(self.settings.trace_dir, trace_id, trace)

    async def _nonverifiable(self, req: KovaRequest, trace: dict[str, Any], governor: CostGovernor) -> KovaResponse:
        worker_models = DEFAULT_FANOUT if req.profile == "ultra" else WORKER_MODELS
        policy = "ultra_full_pool_then_gpt55_judge_synth" if req.profile == "ultra" else "cheap_workers_then_gpt55_judge_synth"
        trace.setdefault("conductor_steps", []).append({"action": "spawn_candidate", "model": "full_pool" if req.profile == "ultra" else "cheap_worker_pool", "reason": "ultra non-verifiable fusion uses the full pool" if req.profile == "ultra" else "adaptive non-verifiable fusion starts with cheap workers"})
        outputs = await asyncio.gather(*[self._call(m, req.prompt, "fanout", trace, governor) for m in worker_models])
        joined = json.dumps(dict(zip(worker_models, outputs)), indent=2)
        trace.setdefault("conductor_steps", []).append({"action": "judge", "model": GPT55, "reason": "judge cheap-worker consensus before synthesis"})
        judge_prompt = f"Produce structured analysis with consensus, contradictions, gaps, insights for these answers:\n{joined}"
        analysis = await self._call(GPT55, judge_prompt, "judge", trace, governor)
        trace.setdefault("conductor_steps", []).append({"action": "synthesize", "model": GPT55, "reason": "write one model-like final answer"})
        synth_prompt = f"Write the final answer to the user prompt using this analysis.\nPrompt:{req.prompt}\nAnalysis:{analysis}"
        answer = await self._call(GPT55, synth_prompt, "synth", trace, governor)
        trace.setdefault("conductor_steps", []).append({"action": "stop", "reason": "non-verifiable synthesis complete"})
        trace["nonverifiable"] = {"fanout_outputs": joined, "analysis": analysis, "adaptive_policy": policy}
        return KovaResponse(answer=answer, verified=False, verifier=None, trace_id=trace["trace_id"], models_called=trace["models_called"], repairs_used=0)

    async def _generate_candidate(self, model: str, prompt: str, trace: dict[str, Any], governor: CostGovernor) -> dict:
        output = await self._call(model, prompt, "candidate", trace, governor)
        files, notes = files_from_model_output(output)
        return {"model": model, "files": files, "notes": notes, "repairs_used": 0, "raw": output}

    async def _verifiable(self, req: KovaRequest, trace: dict[str, Any], governor: CostGovernor) -> KovaResponse:
        assert req.tests is not None
        thinker = await self._call(GPT55, f"Create a crisp implementation spec and constraints for:\n{req.prompt}", "thinker", trace, governor)
        candidate_prompt = ('Implement this task. Return ONLY JSON: {"files":[{"path":"main.py","content":"..."}],"notes":"..."}\n'
                            f"Task:{req.prompt}\nSpec:{thinker}")
        candidates = await asyncio.gather(*[self._generate_candidate(m, candidate_prompt, trace, governor) for m in WORKER_MODELS])
        for cand in candidates:
            verifier = await run_verifier(cand["files"], req.tests)
            cand["verifier"] = verifier.model_dump()
            rounds = 0
            while not verifier.passed and rounds < self.settings.max_repairs_per_candidate:
                rounds += 1
                repair_prompt = build_repair_prompt(req.prompt, cand["files"], verifier.stdout, verifier.stderr)
                trace["repair_prompts"].append({"model": cand["model"], "round": rounds, "prompt": repair_prompt})
                repaired = await self._call(cand["model"], repair_prompt, "repair", trace, governor)
                cand["files"], cand["notes"] = files_from_model_output(repaired)
                cand["repairs_used"] = rounds
                verifier = await run_verifier(cand["files"], req.tests)
                cand["verifier"] = verifier.model_dump()
                if rounds == 1 and not any(c.get("verifier", {}).get("passed") for c in candidates):
                    if self.settings.enable_gpt55_pro and governor.can_call(GPT55_PRO):
                        trace["models_called"].append(GPT55_PRO)
                        trace["model_calls"].append({"model": GPT55_PRO, "purpose": "debugger", "started_ms": _now_ms(), "ended_ms": _now_ms()})
                    trace["cost_governor"] = governor.decisions
            trace["candidates"].append(cand)
        winner, reason = choose_candidate(candidates)
        trace["final_selection_reason"] = reason
        answer = json.dumps({"files": winner["files"], "notes": winner.get("notes", "")}, indent=2, sort_keys=True)
        return KovaResponse(answer=answer, verified=winner["verifier"]["passed"], verifier=winner["verifier"], trace_id=trace["trace_id"], models_called=trace["models_called"], repairs_used=winner.get("repairs_used", 0))
