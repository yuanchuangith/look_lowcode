import { createServer, type Server } from 'node:http';
import { afterEach, describe, expect, it } from 'vitest';
import { getDraftVersion } from '../src/platform/api.js';

const servers: Server[] = [];
afterEach(async () => {
    await Promise.all(servers.splice(0).map(server => new Promise<void>((resolve, reject) => {
        server.close(error => error ? reject(error) : resolve());
        server.closeAllConnections();
    })));
});

async function platform(status: number, body: unknown, location?: string) {
    let requests = 0;
    const server = createServer((_req, res) => {
        requests++;
        res.statusCode = status;
        res.setHeader('content-type', 'application/json');
        if (location)
            res.setHeader('location', location);
        res.end(JSON.stringify(body));
    });
    servers.push(server);
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const address = server.address();
    if (!address || typeof address === 'string')
        throw new Error('Expected local test server');
    return { ctx: { baseUrl: `http://127.0.0.1:${address.port}`, cookie: 'synthetic-session', appId: 'app', siteOutId: 'site' },
        requests: () => requests };
}

describe('development-version authentication failures', () => {
    it.each([401, 403])('reports HTTP %i as authentication failure without retrying the same token', async status => {
        const fixture = await platform(status, { message: 'session expired' });
        await expect(getDraftVersion(fixture.ctx, '/gxp2', 'app', 'site')).rejects.toMatchObject({ status });
        expect(fixture.requests()).toBe(1);
    });

    it.each([401, 403])('recognizes DataResult authentication status %i in an HTTP 200 response', async status => {
        const fixture = await platform(200, { statusCode: status, data: null });
        await expect(getDraftVersion(fixture.ctx, '/gxp2', 'app', 'site')).rejects.toMatchObject({ status });
        expect(fixture.requests()).toBe(1);
    });

    it('does not follow a login redirect or label it as a missing draft version', async () => {
        const fixture = await platform(302, {}, '/login');
        await expect(getDraftVersion(fixture.ctx, '/gxp2', 'app', 'site')).rejects.toMatchObject({ status: 401 });
        expect(fixture.requests()).toBe(1);
    });

    it('keeps a genuinely missing development version blocked', async () => {
        const fixture = await platform(200, { statusCode: 200, data: { appId: 'app', siteOutId: 'site' } });
        await expect(getDraftVersion(fixture.ctx, '/gxp2', 'app', 'site')).rejects.toMatchObject({ code: 'DRAFT_VERSION_UNAVAILABLE' });
        expect(fixture.requests()).toBe(1);
    });

    it('preserves a permanent page error returned with HTTP 500 without retrying it', async () => {
        const fixture = await platform(500, { Error: { Message: 'coreErr:000002 不存在或已删除' } });
        await expect(getDraftVersion(fixture.ctx, '/gxp2', 'app', 'site')).rejects.toThrow('不存在或已删除');
        expect(fixture.requests()).toBe(1);
    });
});
