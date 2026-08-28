import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';

const packageRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const cli = join(packageRoot, 'dist', 'cli.js');

describe('pull --json contract', () => {
    it('returns structured JSON and a non-zero exit code for argument errors', () => {
        const result = spawnSync(process.execPath, [cli, 'pull', '--json', '--page'], {
            encoding: 'utf8',
        });
        const lines = result.stdout.trim().split(/\r?\n/);
        const payload = JSON.parse(lines.at(-1) || '{}');
        expect(result.status).not.toBe(0);
        expect(payload).toMatchObject({
            ok: false,
            counts: {},
            failures: [],
            health: null,
            error: { code: 'INVALID_ARGUMENT' },
        });
        expect(payload).toHaveProperty('mode');
        expect(payload).toHaveProperty('page');
        expect(payload).toHaveProperty('changes');
        expect(payload).toHaveProperty('durationMs');
    });
});
