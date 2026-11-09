#!/bin/bash
# Axeom StudioOS Backend Startup Script
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Starting Axeom StudioOS FastAPI Backend on http://0.0.0.0:8000..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
