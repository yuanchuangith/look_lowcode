#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_COMMAND=${PYTHON:-python3}
RUNTIME_ROOT=$($PYTHON_COMMAND "$SCRIPT_DIR/setup.py" --print-runtime-root)
VENV_PYTHON="$RUNTIME_ROOT/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "Runtime is missing. Run: sh $SCRIPT_DIR/setup.sh" >&2
  exit 1
fi
exec "$VENV_PYTHON" "$SCRIPT_DIR/configure_connection.py" "$@"
