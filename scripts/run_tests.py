from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.setup import _venv_python, runtime_root


def select_python() -> Path:
    runtime_python = _venv_python(runtime_root())
    return runtime_python if runtime_python.is_file() else Path(sys.executable)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Look unittest suite without manual PYTHONPATH setup")
    parser.add_argument("-p", "--pattern", default="test_*.py", help="Test filename pattern")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--live", action="store_true", help="Opt in to read-only live database checks")
    parser.add_argument("--current-python", action="store_true", help="Use this Python instead of the installed Look runtime")
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(arguments)
    python = select_python()
    if not args.current_python and os.path.abspath(python) != os.path.abspath(sys.executable):
        return subprocess.run(
            [str(python), str(Path(__file__).resolve()), "--current-python", *arguments],
            cwd=REPO_ROOT,
        ).returncode

    paths = [str(REPO_ROOT / "mcp"), str(REPO_ROOT / "tests"), str(REPO_ROOT)]
    sys.path[:0] = paths
    inherited = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(paths + ([inherited] if inherited else []))
    os.environ["GXP_LIVE_TEST"] = "1" if args.live else "0"
    os.chdir(REPO_ROOT)
    print(f"[tests] Python: {sys.executable}", flush=True)
    suite = unittest.TestLoader().discover(str(REPO_ROOT / "tests"), pattern=args.pattern)
    if suite.countTestCases() == 0:
        print(f"[ERROR] No tests matched {args.pattern!r}.", file=sys.stderr)
        return 1
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
