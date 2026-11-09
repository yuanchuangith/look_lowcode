"""Generate the explicit, small read-only worker payload for standalone installs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCES = ("config.py", "db.py", "sql_guard.py", "repository.py", "schema_repository.py",
                "cpm_config.py", "cpm_runner.py", "project_refresh.py")


def sync(check=False):
    source = ROOT / "mcp/gxp_core"
    payload = ROOT / "mcp/gxp_project_context/_collectors"
    payload.mkdir(parents=True, exist_ok=True)
    changed = []
    for name in CORE_SOURCES:
        content = (source / name).read_bytes()
        destination = payload / name
        if not destination.is_file() or destination.read_bytes() != content:
            changed.append(name)
            if not check:
                destination.write_bytes(content)
    if check and changed:
        raise SystemExit("Collector mirror differs: " + ", ".join(changed))
    manifest = {"schema_version": 1, "source_package": "gxp_core", "files": [
        {"path": name, "sha256": hashlib.sha256((source / name).read_bytes()).hexdigest()}
        for name in CORE_SOURCES]}
    if not check:
        (payload / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        write_payload = ROOT.parent / "write/mcp/gxp_project_context/_collectors"
        if write_payload.parent.is_dir():
            shutil.copytree(payload, write_payload, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print("Collector source mirror verified" if check else "Collector payload generated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    sync(parser.parse_args().check)
