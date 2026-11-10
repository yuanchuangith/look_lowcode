// 多语言端点（系统-语言管理，2026-08-25 实测，样本 test/fixtures/real/language-*.json）。
// 两个端点：语言条目全量（1477 条，每条自带全部语种翻译）+ 语种字典（languagengine）。
import { platformGet } from './http-client.js';
import { fetchList } from './menus-api.js';
const LANGUAGE_PAGE_SIZE = 100;

/** 语言项包含全部语种翻译，分批读取避免超大响应超过网关超时。 */
export async function getLanguages(ctx, apiPrefix) {
    const rows = [];
    for (let page = 1; ; page++) {
        const batch = await fetchList(ctx, apiPrefix, '/api/language', { page, pageSize: LANGUAGE_PAGE_SIZE });
        rows.push(...batch);
        if (batch.length < LANGUAGE_PAGE_SIZE)
            return rows;
    }
}
/**
 * 语种字典。实测：路径 /inbiz/* 原样（不走 gxp2 前缀，故无 apiPrefix 参数）；
 * 响应是裸数组（无 statusCode 包装）；服务端要求 appid 头（buildHeaders 自动携带）。
 */
export async function getLanguageKinds(ctx) {
    const resp = await platformGet(ctx, '', '/inbiz/api/services/languagengine/v3/kind', { timestamp: Date.now() });
    return Array.isArray(resp) ? resp : (resp?.data ?? []);
}
