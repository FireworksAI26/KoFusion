from __future__ import annotations

import time
from typing import Any
import httpx

from .config import Settings

WORKER_MODELS = ["workers-ai/@cf/moonshotai/kimi-k2.7-code", "workers-ai/@cf/zai-org/glm-5.2"]
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
        url = f"https://gateway.ai.cloudflare.com/v1/{self.settings.cf_account_id}/{self.settings.cf_gateway_id}/compat/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {self.settings.cf_aig_token}", "Content-Type": "application/json"},
                json=payload,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = resp.text[:500].replace(self.settings.cf_aig_token or "", "<redacted>")
                raise RuntimeError(
                    "Cloudflare AI Gateway request failed "
                    f"status={resp.status_code} model={model} gateway={self.settings.cf_gateway_id} "
                    "endpoint=/compat/chat/completions. "
                    "For 401, check CF_AIG_TOKEN, CF_ACCOUNT_ID, CF_GATEWAY_ID, and make sure the workflow is running the latest branch. "
                    f"response={body}"
                ) from exc
            data = resp.json()
        _ = started
        if isinstance(data, dict):
            choices = data.get("choices")
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if isinstance(content, list):
                    return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
                return content or ""
            if "result" in data and isinstance(data["result"], str):
                return data["result"]
            if "response" in data:
                return str(data["response"])
        return str(data)
