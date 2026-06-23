from __future__ import annotations

import time
from typing import Any
import httpx

from .config import Settings

WORKER_MODELS = ["workers-ai/@cf/moonshotai/kimi-k2.6", "workers-ai/@cf/zai-org/glm-5.2"]
GPT55 = "openai/gpt-5.5"
GPT55_PRO = "openai/gpt-5.5-pro"
CLAUDE_OPUS = "anthropic/claude-opus-4.8"
DEFAULT_FANOUT = [*WORKER_MODELS, GPT55]

COST_ESTIMATES_USD = {
    WORKER_MODELS[0]: 0.01,
    WORKER_MODELS[1]: 0.01,
    GPT55: 0.10,
    GPT55_PRO: 5.00,
    CLAUDE_OPUS: 0.50,
}


class CostGovernor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.estimated_spend = 0.0
        self.decisions: list[dict[str, Any]] = []

    def can_call(self, model: str) -> bool:
        estimate = COST_ESTIMATES_USD.get(model, self.settings.hard_dollar_cap_usd + 1.0)
        allowed = self.estimated_spend + estimate <= self.settings.hard_dollar_cap_usd
        if model == GPT55_PRO and not self.settings.enable_gpt55_pro:
            allowed = False
        self.decisions.append({"model": model, "estimate_usd": estimate, "allowed": allowed, "spend_before_usd": self.estimated_spend})
        if allowed:
            self.estimated_spend += estimate
        return allowed


class ModelPool:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def complete(self, model: str, prompt: str, *, purpose: str = "completion") -> str:
        if not (self.settings.cf_account_id and self.settings.cf_aig_token):
            raise RuntimeError("Cloudflare credentials are not configured; tests should monkeypatch ModelPool.complete")
        url = f"https://gateway.ai.cloudflare.com/v1/{self.settings.cf_account_id}/{self.settings.cf_gateway_id}/{model}"
        payload = {"messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers={"Authorization": f"Bearer {self.settings.cf_aig_token}"}, json=payload)
            resp.raise_for_status()
            data = resp.json()
        _ = started
        if isinstance(data, dict):
            if "result" in data and isinstance(data["result"], str):
                return data["result"]
            choices = data.get("choices")
            if choices:
                return choices[0].get("message", {}).get("content", "")
            if "response" in data:
                return str(data["response"])
        return str(data)
