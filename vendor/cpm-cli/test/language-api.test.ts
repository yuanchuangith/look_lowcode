import { beforeEach, describe, expect, it, vi } from 'vitest';

const { fetchList, platformGet } = vi.hoisted(() => ({ fetchList: vi.fn(), platformGet: vi.fn() }));

vi.mock('../src/platform/menus-api.js', () => ({ fetchList }));
vi.mock('../src/platform/http-client.js', () => ({ platformGet }));

import { getLanguages } from '../src/platform/language-api.js';

const ctx = { baseUrl: 'http://example.invalid', appId: 'app', siteOutId: 'site' };

beforeEach(() => {
    fetchList.mockReset();
    platformGet.mockReset();
});

describe('language catalog paging', () => {
    it('loads bounded pages until the final short page', async () => {
        fetchList.mockImplementation(async (_ctx, _prefix, _path, params) => {
            const count = params.page < 3 ? 100 : 27;
            return Array.from({ length: count }, (_, index) => ({ key: `${params.page}:${index}` }));
        });

        const rows = await getLanguages(ctx, '/gxp2');

        expect(rows).toHaveLength(227);
        expect(fetchList).toHaveBeenCalledTimes(3);
        expect(fetchList).toHaveBeenNthCalledWith(1, ctx, '/gxp2', '/api/language', { page: 1, pageSize: 100 });
        expect(fetchList).toHaveBeenNthCalledWith(2, ctx, '/gxp2', '/api/language', { page: 2, pageSize: 100 });
        expect(fetchList).toHaveBeenNthCalledWith(3, ctx, '/gxp2', '/api/language', { page: 3, pageSize: 100 });
    });

    it('returns an empty catalog after the first empty page', async () => {
        fetchList.mockResolvedValue([]);

        await expect(getLanguages(ctx, '/gxp2')).resolves.toEqual([]);
        expect(fetchList).toHaveBeenCalledTimes(1);
    });
});
