#!/usr/bin/env bash
set -euo pipefail
curl -sS http://localhost:8000/v1/kovafusion \
  -H 'content-type: application/json' \
  -d '{"prompt":"Explain KovaFusion in one paragraph.","tests":null,"mode":"nonverifiable"}' | python -m json.tool
