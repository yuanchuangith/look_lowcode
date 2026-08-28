import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { afterEach, describe, expect, it } from 'vitest';

import { writeSnapshot } from '../src/snapshot/writer.js';
import { assertPartialBaseline, loadPageMetadata, PartialBaselineError } from '../src/snapshot/page-meta.js';

const roots: string[] = [];

afterEach(async () => {
    await Promise.all(roots.splice(0).map(root => rm(root, { recursive: true, force: true })));
});

function page(route: string, id: string, outId: string, name: string, flows: any[] = []) {
    return {
        summary: { route, id, outId, name, group: '测试' },
        pageSchema: { content: { schema: { type: 'Form', props: {}, children: [] }, form: {} } },
        flows,
        translations: new Map(),
    };
}

function data(pages: any[], mode = 'full', baselineMetadata: any[] | undefined = undefined) {
    return {
        mode,
        baselineMetadata,
        pages,
        processes: [],
        processGroups: [],
        publicBizflows: [],
        menus: [],
        navigations: [],
        interfaceGroups: [],
        interfaces: [],
        languages: [],
        languageKinds: [],
        models: [],
        dictionaries: [],
        datasets: [],
        events: [],
        failures: [],
        platform: { url: 'https://example.invalid', appId: 'app' },
    };
}

async function baseline() {
    const root = await mkdtemp(join(tmpdir(), 'cpm-partial-'));
    roots.push(root);
    await writeSnapshot(root, data([
        page('/a', 'id-a', 'out-a', '页面A'),
        page('/b', 'id-b', 'out-b', '页面B', [{ id: 'flow-old', code: 'OLD', describe: '旧规则', state: true, codes: { js: 'old' } }]),
    ]));
    return root;
}

describe('safe partial snapshot writes', () => {
    it('preserves non-target pages, removes stale target rules, and rebuilds all indexes', async () => {
        const root = await baseline();
        const loaded = loadPageMetadata(root);
        expect(loaded.errors).toEqual([]);
        const a = loaded.metadata.find(meta => meta.route === '/a');
        const b = loaded.metadata.find(meta => meta.route === '/b');
        const marker = join(root, a.dir, 'kept-marker.txt');
        writeFileSync(marker, 'keep', 'utf8');
        const oldRule = join(root, b.dir, 'bizflows');
        expect(existsSync(oldRule)).toBe(true);

        await writeSnapshot(root, data([page('/b', 'id-b', 'out-b', '页面B')], 'page', loaded.metadata));

        expect(readFileSync(marker, 'utf8')).toBe('keep');
        expect(existsSync(oldRule)).toBe(false);
        for (const name of ['pages.md', 'model-usage.md', 'component-usage.md', 'event-usage.md']) {
            const text = readFileSync(join(root, 'indexes', name), 'utf8');
            if (name === 'pages.md') {
                expect(text).toContain('/a');
                expect(text).toContain('/b');
            }
        }
    });

    it('moves a renamed page only after the replacement is complete', async () => {
        const root = await baseline();
        const before = loadPageMetadata(root).metadata;
        const old = before.find(meta => meta.route === '/b');
        await writeSnapshot(root, data([page('/b', 'id-b', 'out-b', '页面B新名称')], 'page', before));
        const after = loadPageMetadata(root).metadata;
        const renamed = after.find(meta => meta.route === '/b');
        expect(renamed.dir).not.toBe(old.dir);
        expect(existsSync(join(root, renamed.dir, 'page-meta.json'))).toBe(true);
        expect(existsSync(join(root, old.dir))).toBe(false);
    });

    it('rejects old baselines before any snapshot write', async () => {
        const root = await baseline();
        const loaded = loadPageMetadata(root);
        const missing = join(root, loaded.metadata[0].dir, 'page-meta.json');
        rmSync(missing, { force: true });
        const marker = join(root, 'unchanged.txt');
        writeFileSync(marker, 'same', 'utf8');
        expect(() => assertPartialBaseline(root, [
            { route: '/a', id: 'id-a', outId: 'out-a' },
            { route: '/b', id: 'id-b', outId: 'out-b' },
        ])).toThrow(PartialBaselineError);
        expect(readFileSync(marker, 'utf8')).toBe('same');
    });

    it('full pull still removes pages truly deleted by the platform', async () => {
        const root = await baseline();
        const before = loadPageMetadata(root).metadata;
        const removed = before.find(meta => meta.route === '/b');
        await writeSnapshot(root, data([page('/a', 'id-a', 'out-a', '页面A')]));
        expect(existsSync(join(root, removed.dir))).toBe(false);
        expect(readFileSync(join(root, 'indexes', 'pages.md'), 'utf8')).not.toContain('/b');
    });
});
