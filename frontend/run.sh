#!/bin/bash
# Axeom StudioOS Frontend Startup Script
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "Starting Axeom StudioOS Next.js Frontend on http://0.0.0.0:3000..."
npm run start -- -p 3000 -H 0.0.0.0
