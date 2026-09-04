#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
if [ -n "${GXP_LOWCODE_RUNTIME_ROOT:-}" ]; then
  RUNTIME=$GXP_LOWCODE_RUNTIME_ROOT
elif [ "$(uname -s)" = "Darwin" ]; then
  RUNTIME="$HOME/Library/Application Support/GxpLowcodeReadonly"
else
  RUNTIME="${XDG_DATA_HOME:-$HOME/.local/share}/GxpLowcodeReadonly"
fi
PYTHON="$RUNTIME/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Look runtime is missing. Run scripts/setup.sh first." >&2
  exit 1
fi
exec "$PYTHON" "$ROOT/scripts/configure_schema.py" "$@"

