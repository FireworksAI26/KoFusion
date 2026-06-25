# KovaFusion V1

KovaFusion is an OpenAI-compatible FastAPI orchestration backend. It uses an adaptive conductor to route requests to a Cloudflare model pool, optionally verifies executable outputs, performs patch-based bounded repair, selects the best candidate, and writes full JSON traces.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


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

## Run eval report

```bash
scripts/run_eval.sh
```

## Run server

```bash
uvicorn app:app --reload --port 8000
```

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
