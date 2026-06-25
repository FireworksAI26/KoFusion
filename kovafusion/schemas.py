from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class TestFile(BaseModel):
    __test__ = False
    path: str
    content: str


class TestSpec(BaseModel):
    __test__ = False
    language: Literal["python"]
    files: list[TestFile]
    run: str = "python -m pytest -q"
    timeout_sec: int = Field(default=20, ge=1, le=120)


class KovaRequest(BaseModel):
    prompt: str
    tests: TestSpec | None = None
    mode: Literal["auto", "verifiable", "nonverifiable"] = "auto"
    profile: Literal["standard", "ultra"] = "standard"


class VerifierResult(BaseModel):
    passed: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int
    duration_ms: int


class KovaResponse(BaseModel):
    answer: str
    verified: bool
    verifier: VerifierResult | None
    trace_id: str
    models_called: list[str]
    repairs_used: int


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: Literal["kova-atlas", "kova-atlas-ultra"] = "kova-atlas"
    messages: list[ChatMessage]
    temperature: float | None = None
    stream: bool = False
    tests: TestSpec | None = None
    mode: Literal["auto", "verifiable", "nonverifiable"] = "auto"


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: dict[str, int | None]
    kovafusion: KovaResponse
