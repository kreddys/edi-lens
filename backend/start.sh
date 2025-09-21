#!/bin/bash
cd "/workspace/edi-lens/backend"
source venv/bin/activate
source "/workspace/edi-lens/.env.codex"
exec poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
