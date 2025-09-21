#!/bin/bash
cd "/workspace/edi-lens/frontend"
source "/workspace/edi-lens/.env.codex"
exec npm run dev -- --host 0.0.0.0 --port 3000
