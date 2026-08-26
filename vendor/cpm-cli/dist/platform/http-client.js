// 平台 HTTP 客户端：路径重写 / 认证头 / 错误分类 / GET 重试。
// 移植自 D:\code\test\src\tools\action-design-tools\api-client.ts（实证结论保留在注释中）。
import axios from 'axios';
/** 服务不可用：5xx/401/403/无响应。调用方对 GET 可重试，认证失败（status 401/403）应指引重新 login。 */
export class ServiceUnavailableError extends Error {
    unavailable = true;
    status;
    constructor(message, status = undefined) {
        super(message);
        this.name = 'ServiceUnavailableError';
        this.status = status;
    }
}
/**
 * 解析路径补全平台上下文前缀。实证结论（cpm.gxp2.com）：
 *   - /api/pages*          → {apiPrefix}/api/apps/pages*（页面列表走 /apps 子路径）
 *   - 其余 /api/*          → {apiPrefix}{path}
 *   - /inbiz/*、/edoc2Flow-web/*、已带协议 → 原样（引擎直连，不在 /gxp2 下）
 */
export function resolveApiPath(path, apiPrefix) {
    if (/^https?:\/\//i.test(path))
        return path;
    if (!path.startsWith('/api/'))
        return path;
    if (path === '/api/pages' || path.startsWith('/api/pages/')) {
        return apiPrefix ? `${apiPrefix}/api/apps/pages${path.slice('/api/pages'.length)}` : path;
    }
    return apiPrefix ? `${apiPrefix}${path}` : path;
}
function buildUrl(ctx, apiPrefix, path) {
    return `${ctx.baseUrl}${resolveApiPath(path, apiPrefix)}`;
}
function buildHeaders(ctx) {
    // appid/siteoutid 小写是平台网关的约定头名（api-client.ts 实证）
    const h = { Cookie: ctx.cookie };
    if (ctx.appId)
        h['appid'] = ctx.appId;
    if (ctx.siteOutId)
        h['siteoutid'] = ctx.siteOutId;
    return h;
}
/** 与 api-client.ts isServiceUnavailable 同判定：5xx、401/403、无响应 */
function isServiceUnavailable(error) {
    const status = error?.response?.status;
    if (status !== undefined)
        return status >= 500 || status === 401 || status === 403;
    return true; // 无 response：网络中断/超时
}
function toUnavailableError(url, method, error) {
    const status = error?.response?.status;
    const reason = status ? `HTTP ${status}` : `无响应（${error?.message || '网络/超时'}）`;
    return new ServiceUnavailableError(`${method} ${url} 接口暂不可用（${reason}）`, status);
}
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
const GET_RETRIES = 2;
/** GET：幂等请求，对 ServiceUnavailableError 指数退避（1000*2^n ms）重试 2 次 */
export async function platformGet(ctx, apiPrefix, path, params = undefined) {
    const url = buildUrl(ctx, apiPrefix, path);
    for (let attempt = 0;; attempt++) {
        try {
            const resp = await axios.get(url, {
                params, timeout: 30000, headers: buildHeaders(ctx), validateStatus: undefined,
            });
            return resp.data;
        }
        catch (error) {
            if (!isServiceUnavailable(error)) {
                // 业务类 4xx：带状态码与响应摘要抛普通错误，便于定位但不触发重试
                const status = error?.response?.status;
                const body = JSON.stringify(error?.response?.data ?? '').slice(0, 200);
                throw new Error(`GET ${url} 失败: status=${status} body=${body}`);
            }
            if (attempt >= GET_RETRIES)
                throw toUnavailableError(url, 'GET', error);
            await sleep(1000 * 2 ** attempt);
        }
    }
}
/** POST：不重试（非幂等），错误分类与 GET 一致 */
export async function platformPost(ctx, apiPrefix, path, body, contentType = undefined) {
    const url = buildUrl(ctx, apiPrefix, path);
    const headers = { ...buildHeaders(ctx) };
    if (contentType)
        headers['content-type'] = contentType;
    try {
        const resp = await axios.post(url, body, { timeout: 30000, headers });
        return resp.data;
    }
    catch (error) {
        if (isServiceUnavailable(error))
            throw toUnavailableError(url, 'POST', error);
        const status = error?.response?.status;
        const bodySummary = JSON.stringify(error?.response?.data ?? '').slice(0, 200);
        throw new Error(`POST ${url} 失败: status=${status} body=${bodySummary}`);
    }
}
//# sourceMappingURL=http-client.js.map