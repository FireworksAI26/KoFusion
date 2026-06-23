from __future__ import annotations

import os
from dotenv import load_dotenv
from dataclasses import dataclass
from pathlib import Path


load_dotenv()


@dataclass(frozen=True)
class Settings:
    cf_account_id: str | None
    cf_gateway_id: str
    cf_aig_token: str | None
    trace_dir: Path
    max_models_per_request: int
    max_repairs_per_candidate: int
    enable_gpt55_pro: bool
    hard_dollar_cap_usd: float
    max_steps: int = 8


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    return Settings(
        cf_account_id=os.getenv("CF_ACCOUNT_ID"),
        cf_gateway_id=os.getenv("CF_GATEWAY_ID", "default"),
        cf_aig_token=os.getenv("CF_AIG_TOKEN"),
        trace_dir=Path(os.getenv("KOVAFUSION_TRACE_DIR", "./traces")),
        max_models_per_request=int(os.getenv("KOVAFUSION_MAX_MODELS_PER_REQUEST", "6")),
        max_repairs_per_candidate=int(os.getenv("KOVAFUSION_MAX_REPAIRS_PER_CANDIDATE", "2")),
        enable_gpt55_pro=_bool("KOVAFUSION_ENABLE_GPT55_PRO", False),
        hard_dollar_cap_usd=float(os.getenv("KOVAFUSION_HARD_DOLLAR_CAP_USD", "2.00")),
        max_steps=int(os.getenv("KOVAFUSION_MAX_STEPS", "8")),
    )
