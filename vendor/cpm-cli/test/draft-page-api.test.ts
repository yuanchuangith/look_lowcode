import { beforeEach, describe, expect, it, vi } from 'vitest';

const { platformGet } = vi.hoisted(() => ({ platformGet: vi.fn() }));

vi.mock('../src/platform/http-client.js', () => ({
    platformGet,
    ServiceUnavailableError: class ServiceUnavailableError extends Error {},
}));

import { getDraftVersion, getPageList, getPageSchema } from '../src/platform/api.js';

const ctx = { baseUrl: 'https://example.invalid', appId: 'app-a', siteOutId: 'site-a' };
const prefix = '/gxp2';
const draftVersion = 'draft-version';

beforeEach(() => {
    platformGet.mockReset();
});

describe('development draft page API', () => {
    it.each([
        { appId: 'app-a', siteOutId: 'site-a', dataVersionId: draftVersion },
        { AppId: 'app-a', SiteOutId: 'site-a', DataVersionId: draftVersion },
    ])('resolves the current development version from app_info: %j', async info => {
        platformGet.mockResolvedValue({ data: info });

        await expect(getDraftVersion(ctx, prefix, 'app-a', 'site-a')).resolves.toBe(draftVersion);

        expect(platformGet).toHaveBeenCalledOnce();
        expect(platformGet.mock.calls[0].slice(0, 3)).toEqual([ctx, prefix, '/api/app_info']);
    });

    it.each([
        undefined,
        null,
        {},
        { appId: 'app-a', siteOutId: 'site-a' },
        { appId: 'app-a', siteOutId: 'site-a', dataVersionId: '' },
        { appId: 'app-a', siteOutId: 'site-a', dataVersionId: '   ' },
    ])('rejects app_info without an explicit development version: %j', async info => {
        platformGet.mockResolvedValue({ data: info });

        await expect(getDraftVersion(ctx, prefix, 'app-a', 'site-a')).rejects.toThrow();
        expect(platformGet).toHaveBeenCalledOnce();
    });

    it.each([
        { appId: 'other-app', siteOutId: 'site-a', dataVersionId: draftVersion },
        { appId: 'app-a', siteOutId: 'other-site', dataVersionId: draftVersion },
        { AppId: 'other-app', SiteOutId: 'site-a', DataVersionId: draftVersion },
        { AppId: 'app-a', SiteOutId: 'other-site', DataVersionId: draftVersion },
    ])('rejects a development version from a different platform binding: %j', async info => {
        platformGet.mockResolvedValue({ data: info });

        await expect(getDraftVersion(ctx, prefix, 'app-a', 'site-a')).rejects.toThrow();
        expect(platformGet).toHaveBeenCalledOnce();
    });

    it('loads the page catalog for the resolved development version', async () => {
        platformGet.mockResolvedValue([{ Route: '/form-a', Id: 'page-a', OutId: 'out-a', DisplayName: 'Form A' }]);

        const pages = await getPageList(ctx, prefix, 'app-a', 'site-a', draftVersion);

        expect(platformGet).toHaveBeenCalledOnce();
        expect(platformGet).toHaveBeenCalledWith(
            ctx, prefix, '/inbiz/api/services/engines/v3/page/loadTreeList',
            expect.objectContaining({ appId: 'app-a', siteOutId: 'site-a', dataVersionId: draftVersion }),
        );
        expect(pages).toMatchObject([{ route: '/form-a', id: 'page-a', outId: 'out-a' }]);
    });

    it('loads the saved draft schema with explicit editor preview parameters', async () => {
        const savedDraft = { content: { schema: { type: 'Form', props: { title: 'Saved, unpublished change' } } } };
        platformGet.mockResolvedValue({ Component: JSON.stringify(savedDraft) });

        await expect(getPageSchema(ctx, prefix, {
            appId: 'app-a', siteOutId: 'site-a', route: '/form-a', dataVersionId: draftVersion,
        })).resolves.toEqual(savedDraft);

        expect(platformGet).toHaveBeenCalledOnce();
        expect(platformGet).toHaveBeenCalledWith(
            ctx, prefix, '/inbiz/api/services/front/engines/v3/page',
            expect.objectContaining({
                appId: 'app-a', siteOutId: 'site-a', route: '/form-a', dataVersionId: draftVersion,
                isOfficialPreview: false, isAuth: false, isPage: false,
            }),
        );
    });

    it.each([undefined, null, '', '   '])('rejects an absent draft version before fetching a schema: %j', async dataVersionId => {
        await expect(getPageSchema(ctx, prefix, {
            appId: 'app-a', siteOutId: 'site-a', route: '/form-a', dataVersionId,
        })).rejects.toThrow();

        expect(platformGet).not.toHaveBeenCalled();
    });

    it.each([undefined, null, '', '   '])('rejects an absent draft version before fetching the catalog: %j', async dataVersionId => {
        await expect(getPageList(ctx, prefix, 'app-a', 'site-a', dataVersionId)).rejects.toThrow();

        expect(platformGet).not.toHaveBeenCalled();
    });
});
