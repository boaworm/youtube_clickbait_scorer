#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source ytv-env/bin/activate
if [ $# -eq 0 ]; then
    exec python -m src.main --webserver
else
    exec python -m src.main "$@"
fi
