import { readFileSync } from 'node:fs';
import { mkdtemp, rm } from 'node:fs/promises';
import { createServer, type Server } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/commands/fetch-shared.js', () => ({
    fetchSharedChain: async () => ({
        processes: [], processGroups: [], publicBizflows: [],
        menus: [], navigations: [], interfaceGroups: [], interfaces: [],
        languages: [], languageKinds: [], models: [], dictionaries: [], datasets: [], events: [],
    }),
}));

vi.mock('../src/commands/translate-stage.js', () => ({
    translateAll: async (_ctx, _prefix, _gate, pages) => ({ pages, menuTranslations: new Map() }),
    translateTitles: async () => {},
    translateDicts: async (_ctx, _prefix, _gate, dictionaries) => dictionaries,
    recoverLanguageRows: () => null,
}));

import { runPull } from '../src/commands/pull.js';
import { saveConfig, saveTokenCache } from '../src/config/store.js';
import { loadPageMetadata } from '../src/snapshot/page-meta.js';

const roots: string[] = [];
const servers: Server[] = [];
const originalExitCode = process.exitCode;

afterEach(async () => {
    vi.restoreAllMocks();
    process.exitCode = originalExitCode;
    await Promise.all(servers.splice(0).map(server => new Promise<void>((resolve, reject) => {
        server.close(error => error ? reject(error) : resolve());
        server.closeAllConnections();
    })));
    await Promise.all(roots.splice(0).map(root => rm(root, { recursive: true, force: true })));
});

function schema(title: string) {
    return { content: { schema: { type: 'Form', props: { title }, children: [] }, form: {} } };
}

describe('pulling saved, unpublished form changes', () => {
    it('refreshes draft changes and resolves the current development version for every pull', async () => {
        vi.spyOn(console, 'log').mockImplementation(() => {});
        const root = await mkdtemp(join(tmpdir(), 'cpm-draft-pull-'));
        roots.push(root);
        const publishedSchema = schema('Published form');
        let currentDraft = schema('Initial draft');
        let currentVersion = 'draft-v1';
        const requests: { method: string; url: URL }[] = [];
        const server = createServer((req, res) => {
            const url = new URL(req.url || '/', 'http://127.0.0.1');
            requests.push({ method: req.method || '', url });
            res.setHeader('content-type', 'application/json');
            let payload: unknown;
            switch (url.pathname) {
                case '/gxp2/api/app_info':
                    payload = { data: { appId: 'app', siteOutId: 'site', dataVersionId: currentVersion } };
                    break;
                case '/inbiz/api/services/engines/v3/page/loadTreeList':
                    payload = [{ Route: 'form-a', Id: 'page-a', OutId: 'out-a', DisplayName: 'Form A' }];
                    break;
                case '/inbiz/api/services/front/engines/v3/page': {
                    // A default/official request deliberately returns the unchanged published form.
                    const isDraft = url.searchParams.get('dataVersionId') === currentVersion
                        && url.searchParams.get('isOfficialPreview') === 'false';
                    payload = { Component: JSON.stringify(isDraft ? currentDraft : publishedSchema) };
                    break;
                }
                case '/gxp2/api/bizflows/app/form-a':
                    payload = { data: [] };
                    break;
                default:
                    res.statusCode = 404;
                    payload = { error: `Unexpected request: ${url.pathname}` };
            }
            res.end(JSON.stringify(payload));
        });
        servers.push(server);
        await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
        const address = server.address();
        if (!address || typeof address === 'string')
            throw new Error('Expected a local TCP address');
        saveConfig(root, {
            url: `http://127.0.0.1:${address.port}`, apiPrefix: '/gxp2', appId: 'app', siteOutId: 'site',
        });
        saveTokenCache(root, { token: 'test-session', obtainedAt: new Date().toISOString() });

        const readSnapshot = () => {
            const loaded = loadPageMetadata(root);
            expect(loaded.errors).toEqual([]);
            expect(loaded.metadata).toHaveLength(1);
            const meta = loaded.metadata[0];
            return {
                meta,
                page: JSON.parse(readFileSync(join(root, meta.dir, 'page.json'), 'utf8')),
            };
        };
        const expectedSource = () => ({
            version: 'draft', dataVersionId: currentVersion, appId: 'app', siteOutId: 'site',
        });

        const full = await runPull({ cwd: root, json: true });
        expect(full.ok, JSON.stringify(full)).toBe(true);
        expect(full.mode).toBe('full');
        expect(readSnapshot().page).toEqual(currentDraft);
        expect(readSnapshot().meta.designSource).toEqual(expectedSource());
        expect(full.page_design_source).toEqual(expectedSource());

        // Save a change without publishing it; the published schema remains unchanged.
        currentDraft = schema('Saved, unpublished change');
        const page = await runPull({ cwd: root, json: true, page: 'form-a' });
        expect(page.ok, JSON.stringify(page)).toBe(true);
        expect(page.mode).toBe('page');
        expect(readSnapshot().page).toEqual(currentDraft);
        expect(readSnapshot().page).not.toEqual(publishedSchema);
        expect(readSnapshot().meta.designSource).toEqual(expectedSource());

        // A platform version switch must be resolved anew rather than cached after login.
        currentVersion = 'draft-v2';
        currentDraft = schema('Change on the new development version');
        const nextVersion = await runPull({ cwd: root, json: true, page: 'form-a' });
        expect(nextVersion.ok, JSON.stringify(nextVersion)).toBe(true);
        expect(readSnapshot().page).toEqual(currentDraft);
        expect(readSnapshot().meta.designSource).toEqual(expectedSource());
        expect(nextVersion.page_design_source).toEqual(expectedSource());

        expect(requests).toHaveLength(12);
        expect(requests.every(request => request.method === 'GET')).toBe(true);
        expect(requests.filter(request => request.url.pathname === '/gxp2/api/app_info')).toHaveLength(3);
        for (const path of [
            '/inbiz/api/services/engines/v3/page/loadTreeList',
            '/inbiz/api/services/front/engines/v3/page',
        ]) {
            const pageRequests = requests.filter(request => request.url.pathname === path);
            expect(pageRequests.map(request => request.url.searchParams.get('dataVersionId')))
                .toEqual(['draft-v1', 'draft-v1', 'draft-v2']);
            for (const request of pageRequests) {
                expect(request.url.searchParams.get('appId')).toBe('app');
                expect(request.url.searchParams.get('siteOutId')).toBe('site');
            }
        }
        const schemas = requests.filter(request => request.url.pathname === '/inbiz/api/services/front/engines/v3/page');
        for (const request of schemas) {
            expect(request.url.searchParams.get('route')).toBe('form-a');
            for (const flag of ['isOfficialPreview', 'isAuth', 'isPage'])
                expect(request.url.searchParams.get(flag)).toBe('false');
        }
    });
});
