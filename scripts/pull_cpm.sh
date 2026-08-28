#!/bin/sh
set -eu

if ! command -v cpm >/dev/null 2>&1; then
  echo "cpm is not on PATH. Run scripts/setup.sh and add ~/.local/bin to PATH." >&2
  exit 1
fi
exec cpm pull "$@"
