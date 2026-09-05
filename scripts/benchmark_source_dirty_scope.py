from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--implementation-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.implementation_root) / 'mcp'))
    from gxp_core import source_index
    from gxp_core.source_config import SourceRepositoriesConfig, resolve_repository, save_source_config
    results = {}
    with tempfile.TemporaryDirectory(prefix='look-dirty-benchmark-') as temporary:
        root = Path(temporary)
        checkout = root / 'checkout'
        source = checkout / 'src/core/common/service.ts'
        source.parent.mkdir(parents=True)
        source.write_text("export function load(){return request.get('/api/one')}", encoding='utf-8')
        for arguments in [('init', '-q'), ('add', '.'), ('-c', 'user.email=test@example.invalid', '-c', 'user.name=Test', 'commit', '-q', '-m', 'fixture')]:
            subprocess.run(['git', *arguments], cwd=checkout, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=10)
        with patch.dict('os.environ', {'GXP_LOWCODE_SOURCE_CONFIG': str(root/'config.json'), 'GXP_LOWCODE_SOURCE_INDEX': str(root/'index')}), patch('gxp_core.source_config.DEFAULT_REPOSITORIES', {'frontend': (), 'backend': ()}):
            save_source_config(SourceRepositoriesConfig(frontend=(str(checkout),)))
            source_index.refresh_source_index(layers=('frontend',))
            for scenario in ('clean', 'documentation', 'artifact', 'source_edit'):
                if scenario == 'artifact':
                    with (checkout/'artifact.bin').open('wb') as stream:
                        for block in range(64):
                            stream.write(b'x' * 1024 * 1024)
                if scenario == 'source_edit':
                    source.write_text("export function load(){return request.get('/api/seed')}", encoding='utf-8')
                durations, metadata_times, rebuilds = [], [], []
                for iteration in range(5):
                    if scenario == 'documentation':
                        (checkout/'notes.md').write_text(str(iteration), encoding='utf-8')
                    if scenario == 'source_edit':
                        original = source.stat()
                        source.write_text("export function load(){return request.get('/api/" + str(iteration).zfill(4) + "')}", encoding='utf-8')
                        os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
                    started = time.perf_counter()
                    resolve_repository('frontend')
                    metadata_times.append(time.perf_counter() - started)
                    with patch.object(source_index, '_scan_frontend', wraps=source_index._scan_frontend) as scanner:
                        started = time.perf_counter()
                        status = source_index.ensure_source_index(('frontend',))
                        durations.append(time.perf_counter() - started)
                        rebuilds.append(scanner.call_count)
                    if status['repositories']['frontend']['stale']:
                        raise RuntimeError('fixture index remained stale')
                results[scenario] = {'metadata_seconds': metadata_times, 'ensure_seconds': durations, 'rebuild_counts': rebuilds,
                                     'metadata_median': statistics.median(metadata_times), 'ensure_median': statistics.median(durations)}
    output = {'rounds': 5, 'artifact_mib': 64, 'scope': 'temporary_single_file_repository', 'source_edit_contract': 'already_git_dirty_then_same_length_same_mtime_rewrites', 'results': results}
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
