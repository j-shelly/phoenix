#!/usr/bin/env bash
# One-shot setup for Ubuntu / WSL (and any Debian-family Linux).
#
# Ubuntu 23.04+ marks the system Python "externally managed" (PEP 668), so
# `pip install` refuses to run outside a virtual environment. This script
# creates a repo-local venv at .venv/ and installs two-sleeve into it.
#
# Usage:
#   ./scripts/setup.sh          # create .venv and install
#   source .venv/bin/activate   # then, in every new shell you work in
set -euo pipefail

cd "$(dirname "$0")/.."

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "error: python3 >= 3.10 required (found $(python3 --version 2>&1))" >&2
    exit 1
fi

# python3-venv is a separate package on Debian/Ubuntu and WSL images often
# lack it. Detect the failure mode and say exactly what to run.
if ! python3 -m venv .venv 2>/dev/null; then
    echo "python3 -m venv failed — on Ubuntu/WSL install the venv module first:" >&2
    echo "    sudo apt update && sudo apt install -y python3-venv" >&2
    exit 1
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"
.venv/bin/python -m pytest tests/ -q

echo
echo "Setup complete. Activate the environment in each new shell with:"
echo "    source .venv/bin/activate"
echo "then run: two-sleeve scan"
echo "(Without activating, everything still works via .venv/bin/two-sleeve)"
