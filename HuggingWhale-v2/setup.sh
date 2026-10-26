#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
if [ ! -f config.local.json ]; then
  cp config.example.json config.local.json
  chmod 600 config.local.json
fi
echo "Edit config.local.json, configure your AWS profile, then follow QUICKSTART.md."
