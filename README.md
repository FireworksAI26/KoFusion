# KovaFusion V1

KovaFusion is an OpenAI-compatible FastAPI orchestration backend. It uses an adaptive conductor to route requests to a Cloudflare model pool, optionally verifies executable outputs, performs patch-based bounded repair, selects the best candidate, and writes full JSON traces.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```



## iPhone-only Cloudflare smoke test

If you do not have a computer, use GitHub Actions from Safari/GitHub mobile instead of sharing secrets in chat:

1. Open the repo on GitHub.
2. Go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Add `CF_ACCOUNT_ID`, `CF_AIG_TOKEN`, and optionally `CF_GATEWAY_ID`.
4. Go to **Actions → Cloudflare smoke test → Run workflow**.

The workflow runs one low-cost Kimi K2.7 Code smoke call through Cloudflare AI Gateway using GitHub encrypted secrets.

## Local Cloudflare key setup for testing

Do **not** paste your Cloudflare AI token into source code or commit it. Use a local `.env` file instead:

```bash
cp .env.example .env
# edit .env and set CF_ACCOUNT_ID, CF_GATEWAY_ID, and CF_AIG_TOKEN
```

KovaFusion loads `.env` automatically via `python-dotenv`, and `.env` is ignored by git. After filling it in, start the server and run one of the demo scripts:

```bash
uvicorn app:app --reload --port 8000
scripts/demo_nonverifiable.sh
```

## Model pool

KovaFusion uses Cloudflare-hosted models through AI Gateway. The default cheap/open worker pool uses:

- `workers-ai/@cf/moonshotai/kimi-k2.7-code`
- `workers-ai/@cf/zai-org/glm-5.2`

The closed ceiling remains `openai/gpt-5.5`, with optional gated `openai/gpt-5.5-pro`.

## Environment variables

```bash
export CF_ACCOUNT_ID="your-account-id"
export CF_GATEWAY_ID="default"             # optional; defaults to default
export CF_AIG_TOKEN="your-cloudflare-ai-gateway-token"
export KOVAFUSION_TRACE_DIR="./traces"     # optional
export KOVAFUSION_MAX_MODELS_PER_REQUEST=6 # optional
export KOVAFUSION_MAX_REPAIRS_PER_CANDIDATE=2 # optional
export KOVAFUSION_ENABLE_GPT55_PRO=false   # optional
export KOVAFUSION_HARD_DOLLAR_CAP_USD=2.00 # optional
export KOVAFUSION_MAX_STEPS=8          # optional adaptive conductor step budget
```

All real model calls go through Cloudflare AI Gateway. Tests monkeypatch the model layer and do not require keys.

## Run tests

```bash
pytest -q
```


## iPhone benchmark workflow

After adding `CF_ACCOUNT_ID`, `CF_AIG_TOKEN`, and optionally `CF_GATEWAY_ID` as GitHub Actions secrets, run **Actions → Cloudflare KovaFusion benchmarks → Run workflow**. The workflow runs local unit tests plus live Cloudflare benchmarks for:

- **Kova Atlas** (`kova-atlas`) non-verifiable fusion
- **Kova Atlas Ultra** (`kova-atlas-ultra`) non-verifiable fusion
- **Kova Atlas** (`kova-atlas`) verifiable Python repair/verification

It uploads `evals/cloudflare_benchmark_report.md` and trace JSON files as a workflow artifact.

## Run eval report

```bash
scripts/run_eval.sh
```

## Run server

```bash
uvicorn app:app --reload --port 8000
```


## OpenAI-compatible model endpoint

KovaFusion can be called like a single model through an OpenAI-style endpoint. Use **Kova Atlas** (`kova-atlas`) for the efficient profile and **Kova Atlas Ultra** (`kova-atlas-ultra`) for the higher-budget profile:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"kova-atlas","messages":[{"role":"user","content":"Explain KovaFusion in one paragraph."}]}'
```

The response includes normal `choices[0].message.content` plus a `kovafusion` metadata object with trace ID, models called, verification status, and repair count.

Ultra example:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"kova-atlas-ultra","messages":[{"role":"user","content":"Compare Fusion and Atlas Ultra style orchestration."}]}'
```


## Add KovaFusion to your site

Deploy the FastAPI app somewhere your website can reach it, then point your frontend at the OpenAI-compatible endpoint:

```js
const response = await fetch("https://YOUR-KOVAFUSION-DOMAIN/v1/chat/completions", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({
    model: "kova-atlas", // or "kova-atlas-ultra"
    messages: [{ role: "user", content: "Explain KovaFusion in one paragraph." }]
  })
});
const data = await response.json();
console.log(data.choices[0].message.content);
console.log(data.kovafusion.trace_id);
```

Useful site integration endpoints:

- `GET /healthz` checks whether the backend is up.
- `GET /v1/models` returns `kova-atlas` and `kova-atlas-ultra` for model pickers.
- `POST /v1/chat/completions` is the OpenAI-compatible generation endpoint.

For production, set `KOVAFUSION_CORS_ALLOW_ORIGINS` to your site origin, for example:

```bash
export KOVAFUSION_CORS_ALLOW_ORIGINS="https://your-site.com"
```


## Production readiness vs Fable 5

Kova Atlas should only go live on your site after the **Cloudflare KovaFusion benchmarks** workflow passes with your real Cloudflare keys and you compare the report against your Fable 5 baseline. Treat it as production-ready when:

- `Cloudflare smoke test` passes.
- `Cloudflare KovaFusion benchmarks` passes.
- `evals/cloudflare_benchmark_report.md` shows Kova Atlas or Kova Atlas Ultra beating your Fable 5 target on quality/pass rate.
- The average model calls and cost are acceptable for your budget.
- `KOVAFUSION_CORS_ALLOW_ORIGINS` is set to your real site URL, not `*`.
- `KOVAFUSION_HARD_DOLLAR_CAP_USD` is set to a safe production cap.

If it does not beat Fable 5 in the benchmark report, keep it in staging and improve prompts/routing before sending real users to it.

## Demo scripts

```bash
scripts/demo_nonverifiable.sh
scripts/demo_verifiable_python.sh
```

## curl examples

### Non-verifiable

```bash
curl -sS http://localhost:8000/v1/kovafusion \
  -H 'content-type: application/json' \
  -d '{"prompt":"Explain KovaFusion in one paragraph.","tests":null,"mode":"nonverifiable"}'
```

### Verifiable Python

```bash
curl -sS http://localhost:8000/v1/kovafusion \
  -H 'content-type: application/json' \
  -d '{"prompt":"Create main.py with add(a,b).","mode":"verifiable","tests":{"language":"python","files":[{"path":"test_main.py","content":"from main import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"}],"run":"python -m pytest -q","timeout_sec":20}}'
```

## Trace lookup

Each request returns a `trace_id`. Fetch it with:

```bash
curl -sS http://localhost:8000/v1/kovafusion/trace/<trace_id>
```
