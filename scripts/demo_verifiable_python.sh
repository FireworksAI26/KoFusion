#!/usr/bin/env bash
set -euo pipefail
curl -sS http://localhost:8000/v1/kovafusion \
  -H 'content-type: application/json' \
  -d '{"prompt":"Create main.py with add(a,b).","mode":"verifiable","tests":{"language":"python","files":[{"path":"test_main.py","content":"from main import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"}],"run":"python -m pytest -q","timeout_sec":20}}' | python -m json.tool
