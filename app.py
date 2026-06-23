from fastapi import FastAPI, HTTPException
from kovafusion.config import get_settings
from kovafusion.logging import read_trace
from kovafusion.orchestrator import Orchestrator
from kovafusion.schemas import KovaRequest, KovaResponse

app = FastAPI(title="KovaFusion V1")


@app.post("/v1/kovafusion", response_model=KovaResponse)
async def kovafusion(req: KovaRequest) -> KovaResponse:
    return await Orchestrator(get_settings()).run(req)


@app.get("/v1/kovafusion/trace/{trace_id}")
async def get_trace(trace_id: str):
    trace = read_trace(get_settings().trace_dir, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace
