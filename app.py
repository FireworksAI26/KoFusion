import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kovafusion.config import get_settings
from kovafusion.logging import read_trace
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import ChatChoice, ChatCompletionRequest, ChatCompletionResponse, ChatMessage, KovaRequest, KovaResponse

app = FastAPI(title="KovaFusion V1")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_CATALOG = [
    {"id": "kova-atlas", "name": "Kova Atlas", "object": "model", "owned_by": "kovafusion", "description": "Kova Atlas efficient orchestration profile."},
    {"id": "kova-atlas-ultra", "name": "Kova Atlas Ultra", "object": "model", "owned_by": "kovafusion", "description": "Kova Atlas Ultra higher-budget orchestration profile."},
]


@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "kovafusion", "models": [model["id"] for model in MODEL_CATALOG]}


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": MODEL_CATALOG}


@app.post("/v1/kovafusion", response_model=KovaResponse)
async def kovafusion(req: KovaRequest) -> KovaResponse:
    return await Orchestrator(settings).run(req)


def _chat_prompt(messages: list[ChatMessage]) -> str:
    return "\n".join(f"{m.role}: {m.content}" for m in messages)


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(req: ChatCompletionRequest) -> ChatCompletionResponse:
    if req.stream:
        raise HTTPException(status_code=400, detail="streaming is not implemented for KovaFusion V1")
    profile = "ultra" if req.model == "kova-atlas-ultra" else "standard"
    kova_req = KovaRequest(prompt=_chat_prompt(req.messages), tests=req.tests, mode=req.mode, profile=profile)
    kova_resp = await Orchestrator(settings).run(kova_req)
    return ChatCompletionResponse(
        id=f"chatcmpl-{kova_resp.trace_id}",
        created=int(time.time()),
        model=req.model,
        choices=[ChatChoice(index=0, message=ChatMessage(role="assistant", content=kova_resp.answer))],
        usage={"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
        kovafusion=kova_resp,
    )


@app.get("/v1/kovafusion/trace/{trace_id}")
async def get_trace(trace_id: str):
    trace = read_trace(settings.trace_dir, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace
